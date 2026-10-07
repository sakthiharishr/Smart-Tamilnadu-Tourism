from ui.components.chatbot_widget import format_message


def test_bold_and_bullets_become_html():
    html = format_message("Tenkasi has falls.\n- **Courtallam**: main falls\n- **Five Falls**")
    assert html == ("<p>Tenkasi has falls.</p>"
                    "<ul><li><strong>Courtallam</strong>: main falls</li><li><strong>Five Falls</strong></li></ul>")


def test_numbered_list_stays_numbered():
    assert format_message("1. Day one\n2. Day two") == "<ol><li>Day one</li><li>Day two</li></ol>"


def test_html_in_answers_is_escaped():
    assert format_message("<script>x</script> **ok**") == "<p>&lt;script&gt;x&lt;/script&gt; <strong>ok</strong></p>"


def test_chatbot_budget_place_query_returns_places():
    from services.chatbot.chatbot import generate_response
    response = generate_response("i have budget of 10000, suggest me places")
    assert response is not None
    assert "budget" in response.lower()
    assert "- **" in response  # has place recommendations


def test_chatbot_generic_suggest_places_returns_recommendations():
    from services.chatbot.chatbot import generate_response
    response = generate_response("suggest me places")
    assert response is not None
    assert "- **" in response  # has place recommendations

