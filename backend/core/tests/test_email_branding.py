from html.parser import HTMLParser

import pytest

from core import email_utils


class EmailLinks(HTMLParser):
    def __init__(self, content):
        super().__init__()
        self.links = []
        self.images = []
        self.feed(content)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a":
            self.links.append(attrs)
        if tag == "img":
            self.images.append(attrs)


@pytest.fixture
def render_builtin(monkeypatch, settings):
    settings.CISO_ASSISTANT_URL = "https://grc.example.test"
    original_load = email_utils.load_email_template
    monkeypatch.setattr(email_utils, "is_email_template_enabled", lambda _: True)
    monkeypatch.setattr(
        email_utils,
        "load_email_template",
        lambda name, locale: original_load(name, locale, builtin_only=True),
    )
    return email_utils.render_email_template


@pytest.mark.parametrize("locale", ["en", "fr", "de"])
@pytest.mark.parametrize(
    "name,key,path",
    [
        ("password_reset", "reset_password_url", "password-reset/confirm"),
        ("welcome", "set_password_url", "first-connexion"),
        ("welcome_sso", "ciso_assistant_url", "login"),
        ("questionnaire_assignment", "questionnaire_url", "questionnaires/123"),
    ],
)
def test_branded_auth_email_preserves_action_url(
    render_builtin, locale, name, key, path
):
    url = f"https://grc.example.test/{path}?uidb64=abc&token=def-123"
    rendered = render_builtin(name, {key: url}, locale=locale)
    parsed = EmailLinks(rendered["html_body"])
    buttons = [link for link in parsed.links if link.get("class") == "email-btn"]
    assert len(buttons) == 1
    assert buttons[0]["href"] == url
    assert url in rendered["body"]
    assert "10A GRC Lab" in rendered["subject"]
    assert "intuitem.com" not in rendered["html_body"]
    assert f'lang="{locale}"' in rendered["html_body"]
    assert all(
        img["src"].startswith("https://grc.example.test/images/email/")
        for img in parsed.images
    )


def test_email_shell_preserves_escaped_context_and_custom_content(
    monkeypatch, settings
):
    settings.CISO_ASSISTANT_URL = "https://grc.example.test"
    monkeypatch.setattr(email_utils, "is_email_template_enabled", lambda _: True)
    monkeypatch.setattr(
        email_utils,
        "load_email_template",
        lambda *_: {
            "subject": "Notice: $name",
            "body": "Hello **$name**.\n\n$task_list",
        },
    )
    rendered = email_utils.render_email_template(
        "custom_notice",
        {
            "name": "<script>alert(1)</script>",
            "task_list": email_utils.MarkdownSafe(
                "[Review task](https://grc.example.test/tasks/123)"
            ),
        },
        locale="en",
    )
    assert "<script>" not in rendered["html_body"]
    assert "&lt;script&gt;" in rendered["html_body"]
    assert "<strong>" in rendered["html_body"]
    assert any(
        link.get("href") == "https://grc.example.test/tasks/123"
        for link in EmailLinks(rendered["html_body"]).links
    )
    assert "<html" not in rendered["body"]


@pytest.mark.parametrize(
    "template_path", sorted(email_utils.TEMPLATE_BASE_PATH.glob("*/*.yaml"))
)
def test_all_builtin_notifications_use_lab_brand(template_path):
    template = email_utils.load_email_template(
        template_path.stem, template_path.parent.name, builtin_only=True
    )
    assert template is not None
    assert "10A GRC Lab" in template["subject"]
    assert "CISO Assistant" not in template["body"]
    assert "CISO-Assistant" not in template["body"]


@pytest.mark.parametrize("locale", ["en", "fr"])
@pytest.mark.parametrize(
    "template,path",
    [
        (
            "registration/password_reset_email.html",
            "/password-reset/confirm?uidb64=abc&token=def-123",
        ),
        (
            "registration/first_connexion_email.html",
            "/first-connexion?uidb64=abc&token=def-123",
        ),
        ("registration/first_connexion_email_sso.html", ""),
        ("tprm/third_party_email.html", "/questionnaires/123"),
    ],
)
def test_legacy_email_fallback_keeps_branded_shell_and_action(template, path, locale):
    from django.template.loader import render_to_string
    from django.utils.translation import override

    root_url = "https://grc.example.test"
    with override(locale):
        html = render_to_string(
            template,
            {
                "root_url": root_url,
                "uid": "abc",
                "token": "def-123",
                "object": "questionnaires",
                "object_id": "123",
            },
        )
    parsed = EmailLinks(html)
    assert any(link.get("href") == root_url + path for link in parsed.links)
    assert "10A GRC Lab" in html
    assert "CISO Assistant" not in html
    assert "intuitem.com" not in html
    assert f'lang="{locale}"' in html
    assert parsed.images
    assert all(
        img["src"].startswith(root_url + "/images/email/") for img in parsed.images
    )
