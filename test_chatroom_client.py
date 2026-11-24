import unittest

from chatroom_client import format_incoming, valid_message, valid_username


class ChatroomClientTests(unittest.TestCase):
    def test_username_validation_matches_protocol(self):
        self.assertTrue(valid_username("Ada7"))
        self.assertFalse(valid_username(""))
        self.assertFalse(valid_username("abcdefghijklmnopq"))
        self.assertFalse(valid_username("Ada_7"))

    def test_message_validation_preserves_spaces_and_rejects_line_breaks(self):
        self.assertTrue(valid_message("hello  there"))
        self.assertTrue(valid_message(""))
        self.assertFalse(valid_message("line\nbreak"))
        self.assertFalse(valid_message("x" * 1001))

    def test_pushes_are_formatted_without_losing_message_spaces(self):
        self.assertEqual(
            format_incoming("PUBLIC Ada hello  there"),
            "[public] Ada: hello  there",
        )
        self.assertEqual(
            format_incoming("PRIVATE Ada "),
            "[private] Ada: ",
        )
        self.assertEqual(format_incoming("JOINED Ada"), "* Ada joined the chatroom")


if __name__ == "__main__":
    unittest.main()
