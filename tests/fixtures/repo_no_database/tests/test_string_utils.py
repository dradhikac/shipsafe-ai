from string_utils import slugify, capitalize_words


def test_slugify():
    assert slugify("Hello World") == "hello-world"


def test_capitalize():
    assert capitalize_words("hello world") == "Hello World"
