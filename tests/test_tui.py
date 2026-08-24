import asyncio

from textual.widgets import DataTable, Select, TabbedContent

from nandatown.tui import TownApp


def run_async(coro):
    return asyncio.run(coro)


def test_app_mounts_with_all_tabs(tmp_path):
    async def go():
        app = TownApp(out_dir=str(tmp_path))
        async with app.run_test() as pilot:
            for tab in ["tab-town", "tab-run", "tab-agents",
                        "tab-protocols", "tab-services", "tab-evidence"]:
                assert app.query_one(f"#{tab}")
            status = app.query_one("#town-status").render()
            assert "12 protocol layers" in str(status)
            await pilot.pause()

    run_async(go())


def test_lab_run_from_the_run_tab(tmp_path):
    async def go():
        app = TownApp(out_dir=str(tmp_path))
        async with app.run_test() as pilot:
            app.query_one(TabbedContent).active = "tab-run"
            await pilot.pause()
            app.query_one("#run-target", Select).value = "voting"
            await pilot.pause()
            await pilot.click("#run-go")
            await app.workers.wait_for_complete()
            await pilot.pause()
            stages = app.query_one("#run-stages", DataTable)
            assert stages.row_count >= 4
            bundles = app.query_one("#bundle-table", DataTable)
            assert bundles.row_count == 1

    run_async(go())


def test_evidence_verify_from_the_evidence_tab(tmp_path):
    from nandatown.sim.runner import run_lab

    run_lab("voting", str(tmp_path))

    async def go():
        app = TownApp(out_dir=str(tmp_path))
        async with app.run_test() as pilot:
            app.query_one(TabbedContent).active = "tab-evidence"
            await pilot.pause()
            bundles = app.query_one("#bundle-table", DataTable)
            assert bundles.row_count == 1
            await pilot.click("#ev-verify")
            await pilot.pause()

    run_async(go())
