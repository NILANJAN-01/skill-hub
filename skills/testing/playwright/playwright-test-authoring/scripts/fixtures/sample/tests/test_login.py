import time
from playwright.sync_api import Page, expect


def test_login(page: Page):
    page.goto("/login")
    time.sleep(2)
    page.get_by_label("Email").fill("user@example.com")
    page.get_by_role("button", name="Sign in").click(force=True)
    assert page.get_by_text("Welcome").is_visible()
    expect(page.get_by_role("heading", name="Dashboard")).to_be_visible()
