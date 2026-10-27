"""The dashboard page: a normal refresh picks up a new build."""

from factory_server.app import DASHBOARD_DIR


def test_the_page_is_revalidated_on_every_load_so_a_refresh_picks_up_a_new_build(client):
    for path in ("/", "/index.html"):
        page = client.get(path)

        assert page.status_code == 200
        assert "<div id=\"root\">" in page.text or "id=\"root\"" in page.text
        assert page.headers["cache-control"] == "no-cache"


def test_hashed_assets_stay_cacheable(client):
    asset = next((DASHBOARD_DIR / "assets").glob("index-*.js"))

    response = client.get(f"/assets/{asset.name}")

    assert response.status_code == 200
    assert "no-cache" not in response.headers.get("cache-control", "")
