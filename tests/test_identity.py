import json

import httpx
import pytest

from nandatown.bundle import load_bundle, verify_bundle
from nandatown.identity_portable import (
    IdentityError,
    Keystore,
    resolve_eth,
    resolve_file,
    session_proof,
    verify_grant,
    verify_signature,
)
from nandatown.runner import run_town


def stage(result, name):
    return next(s for s in result.stages if s.name == name)


def test_keystore_identity_and_registry(tmp_path):
    ks = Keystore(str(tmp_path))
    identity = ks.new_identity("seller")
    again = ks.new_identity("seller")
    assert identity["agent_id"] == again["agent_id"]
    assert identity["agent_id"].startswith("did:town:")
    resolved = resolve_file(ks.registry_path, identity["agent_id"])
    assert resolved == identity["controller_public"]
    with pytest.raises(IdentityError):
        resolve_file(ks.registry_path, "did:town:missing")


def test_grant_chain_verifies_and_rejects(tmp_path):
    ks = Keystore(str(tmp_path))
    identity = ks.new_identity("seller")
    bundle = ks.make_grant("seller", "run-1")
    proof = session_proof(bundle["session_private"], "run-1", "seller")
    verify_grant(bundle["grant"], bundle["grant_signature"],
                 identity["controller_public"], "run-1", "seller", proof)
    with pytest.raises(IdentityError):
        verify_grant(bundle["grant"], bundle["grant_signature"],
                     identity["controller_public"], "run-2", "seller",
                     proof)
    other = Keystore(str(tmp_path / "other"))
    impostor = other.new_identity("impostor")
    with pytest.raises(IdentityError):
        verify_grant(bundle["grant"], bundle["grant_signature"],
                     impostor["controller_public"], "run-1", "seller",
                     proof)
    expired = ks.make_grant("seller", "run-1", ttl=-1)
    with pytest.raises(IdentityError):
        verify_grant(expired["grant"], expired["grant_signature"],
                     identity["controller_public"], "run-1", "seller",
                     session_proof(expired["session_private"], "run-1",
                                   "seller"))


def test_controller_key_never_in_grant(tmp_path):
    ks = Keystore(str(tmp_path))
    ks.new_identity("seller")
    private = open(ks._key_path("seller")).read().strip()
    bundle = ks.make_grant("seller", "run-1")
    assert private not in json.dumps(bundle)


def test_signature_helper_rejects_garbage():
    assert verify_signature("00" * 32, {"a": 1}, "ff" * 64) is False


def test_eth_resolver_decodes_dynamic_bytes():
    key = b"\x11" * 32

    def responder(request):
        body = json.loads(request.content)
        assert body["method"] == "eth_call"
        assert body["params"][0]["to"] == "0xregistry"
        encoded = (b"\x00" * 31 + b"\x20"
                   + len(key).to_bytes(32, "big") + key)
        return httpx.Response(200, json={
            "jsonrpc": "2.0", "id": 1,
            "result": "0x" + encoded.hex()})

    resolved = resolve_eth("http://rpc", "0xregistry", "0xabcdef12",
                           "did:town:x",
                           http=httpx.Client(
                               transport=httpx.MockTransport(responder)))
    assert resolved == key.hex()


def test_track_run_with_portable_identity(tmp_path):
    bundle_dir, result = run_town("quote-clean", str(tmp_path / "runs"),
                                  identity_dir=str(tmp_path / "keys"))
    detail = [(s.name, s.status, s.note) for s in result.stages]
    assert result.verdict == "passed", detail
    identity_stage = stage(result, "portable_identity")
    assert identity_stage.status == "passed", detail
    assert "did:town:" in identity_stage.note
    bundle = load_bundle(bundle_dir)
    kinds = [e.kind for e in bundle["events"]]
    assert kinds.count("portable_identity_verified") == 2
    assert verify_bundle(bundle_dir) == []


def test_bundles_carry_signed_attestations(tmp_path):
    bundle_dir, _ = run_town("quote-clean", str(tmp_path))
    with open(f"{bundle_dir}/attestation.json") as f:
        attestation = json.load(f)
    assert attestation["payload"]["signer"].startswith("did:town:")
    assert verify_bundle(bundle_dir) == []
    attestation["payload"]["verdict"] = "failed"
    with open(f"{bundle_dir}/attestation.json", "w") as f:
        json.dump(attestation, f)
    problems = verify_bundle(bundle_dir)
    assert any("attestation" in p for p in problems)
