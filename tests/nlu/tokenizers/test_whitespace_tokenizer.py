import pytest

from rasa.nlu.constants import TOKENS_NAMES, TEXT, INTENT, MESSAGE_ACTION_NAME, ACTION_TEXT
from rasa.nlu.training_data import TrainingData, Message
from rasa.nlu.tokenizers.whitespace_tokenizer import WhitespaceTokenizer


@pytest.mark.parametrize(
    "text, expected_tokens, expected_indices",
    [
        (
            "Forecast for lunch",
            ["Forecast", "for", "lunch"],
            [(0, 8), (9, 12), (13, 18)],
        ),
        (
            "hey ńöñàśçií how're you?",
            ["hey", "ńöñàśçií", "how", "re", "you"],
            [(0, 3), (4, 12), (13, 16), (17, 19), (20, 23)],
        ),
        (
            "50 क्या आपके पास डेरी मिल्क 10 वाले बॉक्स मिल सकते है",
            [
                "50",
                "क्या",
                "आपके",
                "पास",
                "डेरी",
                "मिल्क",
                "10",
                "वाले",
                "बॉक्स",
                "मिल",
                "सकते",
                "है",
            ],
            [
                (0, 2),
                (3, 7),
                (8, 12),
                (13, 16),
                (17, 21),
                (22, 27),
                (28, 30),
                (31, 35),
                (36, 41),
                (42, 45),
                (46, 50),
                (51, 53),
            ],
        ),
        (
            "https://www.google.com/search?client=safari&rls=en&q=i+like+rasa&ie=UTF-8&oe=UTF-8 https://rasa.com/docs/nlu/components/#tokenizer-whitespace",
            [
                "https://www.google.com/search?"
                "client=safari&rls=en&q=i+like+rasa&ie=UTF-8&oe=UTF-8",
                "https://rasa.com/docs/nlu/components/#tokenizer-whitespace",
            ],
            [(0, 82), (83, 141)],
        ),
        (
            "Joselico gracias Dois 🙏🇺🇸🏦🛠🔥⭐️🦅👑💪",
            ["Joselico", "gracias", "Dois"],
            [(0, 8), (9, 16), (17, 21)],
        ),
        (":)", [":)"], [(0, 2)]),
        ("Hi :-)", ["Hi"], [(0, 2)]),
    ],
)
def test_whitespace(text, expected_tokens, expected_indices):

    tk = WhitespaceTokenizer()

    tokens = tk.tokenize(Message(text), attribute=TEXT)

    assert [t.text for t in tokens] == expected_tokens
    assert [t.start for t in tokens] == [i[0] for i in expected_indices]
    assert [t.end for t in tokens] == [i[1] for i in expected_indices]


@pytest.mark.parametrize(
    "text, expected_tokens",
    [
        ("Forecast_for_LUNCH", ["Forecast_for_LUNCH"]),
        ("Forecast for LUNCH", ["Forecast for LUNCH"]),
    ],
)
def test_custom_intent_symbol(text, expected_tokens):
    component_config = {"intent_tokenization_flag": True, "intent_split_symbol": "+"}

    tk = WhitespaceTokenizer(component_config)

    message = Message(text)
    message.set(INTENT, text)

    tk.train(TrainingData([message]))

    assert [t.text for t in message.get(TOKENS_NAMES[INTENT])] == expected_tokens


@pytest.mark.parametrize(
    "text, component_config, expected_tokens",
    [
        ("Forecast for LUNCH", {}, ["Forecast", "for", "LUNCH"]),
        ("Forecast for LUNCH", {"case_sensitive": False}, ["forecast", "for", "lunch"]),
        ("Forecast for LUNCH", {"case_sensitive": True}, ["Forecast", "for", "LUNCH"]),
    ],
)
def test_whitespace_with_case(text, component_config, expected_tokens):

    tk = WhitespaceTokenizer(component_config)

    message = Message(text)

    tokens = tk.tokenize(message, attribute=TEXT)

    assert [t.text for t in tokens] == expected_tokens


def test_whitespace_training(supervised_embeddings_config):
    examples = [
        Message(
            "Any Mexican restaurant will do",
            {
                "intent": "restaurant_search",
                "entities": [
                    {"start": 4, "end": 11, "value": "Mexican", "entity": "cuisine"}
                ],
            },
        ),
        Message(
            "I want Tacos!",
            {
                "intent": "restaurant_search",
                "entities": [
                    {"start": 7, "end": 12, "value": "Mexican", "entity": "cuisine"}
                ],
            },
        ),
        Message(
            "action_restart",
            {
                "action_name": "action_restart"
            },
        ),
        Message(
            "Where are you going?",
            {
                MESSAGE_ACTION_NAME: "Where are you going?",
                ACTION_TEXT: "Where are you going?"

            },
        ),
    ]

    component_config = {"case_sensitive": False}
    tk = WhitespaceTokenizer(component_config)

    tk.train(TrainingData(training_examples=examples), supervised_embeddings_config)

    assert examples[0].data.get(TOKENS_NAMES[TEXT])[0].text == "any"
    assert examples[0].data.get(TOKENS_NAMES[TEXT])[1].text == "mexican"
    assert examples[0].data.get(TOKENS_NAMES[TEXT])[2].text == "restaurant"
    assert examples[0].data.get(TOKENS_NAMES[TEXT])[3].text == "will"
    assert examples[0].data.get(TOKENS_NAMES[TEXT])[4].text == "do"
    assert examples[1].data.get(TOKENS_NAMES[TEXT])[0].text == "i"
    assert examples[1].data.get(TOKENS_NAMES[TEXT])[1].text == "want"
    assert examples[1].data.get(TOKENS_NAMES[TEXT])[2].text == "tacos"
    assert examples[2].data.get(TOKENS_NAMES[MESSAGE_ACTION_NAME])[0].text == "action"
    assert examples[2].data.get(TOKENS_NAMES[MESSAGE_ACTION_NAME])[1].text == "restart"
    assert examples[2].data.get(TOKENS_NAMES[TEXT])[0].text == "action_restart"
    assert examples[2].data.get(TOKENS_NAMES[ACTION_TEXT]) is None
    assert examples[3].data.get(TOKENS_NAMES[ACTION_TEXT])[0].text == "where"
    assert examples[3].data.get(TOKENS_NAMES[ACTION_TEXT])[1].text == "are"
    assert examples[3].data.get(TOKENS_NAMES[ACTION_TEXT])[2].text == "you"
    assert examples[3].data.get(TOKENS_NAMES[ACTION_TEXT])[3].text == "going"


def test_whitespace_processing_with_attribute(supervised_embeddings_config):
    message = Message("Any Mexican restaurant will do", {"intent": "restaurant_search", "entities": [
                    {"start": 4, "end": 11, "value": "Mexican", "entity": "cuisine"}],
            },)
    expected_tokens_intent = ["restaurant_search"]
    expected_tokens_text = ["any", "mexican", "restaurant", "will", "do"]
    component_config = {"case_sensitive": False}
    tk = WhitespaceTokenizer(component_config)
    tk.process(message, INTENT)
    tokens_intent = message.get(TOKENS_NAMES[INTENT])
    tk.process(message, TEXT)
    tokens_text = message.get(TOKENS_NAMES[TEXT])
    assert [t.text for t in tokens_intent] == expected_tokens_intent
    assert [t.text for t in tokens_text] == expected_tokens_text

    message = Message("Where are you going?", {MESSAGE_ACTION_NAME: "Where are you going?", ACTION_TEXT: "Where are you going?"},)
    expected_action_tokens_text = ["where", "are", "you", "going"]
    component_config = {"case_sensitive": False}
    tk = WhitespaceTokenizer(component_config)
    tk.process(message, ACTION_TEXT)
    tokens_action_text = message.get(TOKENS_NAMES[ACTION_TEXT])
    tk.process(message, TEXT)
    tokens_text = message.get(TOKENS_NAMES[TEXT])
    assert [t.text for t in tokens_action_text] == expected_action_tokens_text
    assert [t.text for t in tokens_text] == expected_action_tokens_text
