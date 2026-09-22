import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.parser import parse_transcript, find_segment_for_quote
from src.analysis import verify_quote, verify_quote_and_timestamp

SAMPLE_TRANSCRIPT = """Expert 1 – Dr. Jean Martin
Role: Head of Urology
Market: France

00:00
Interviewer: Thanks for joining. To begin, how would you describe robotic surgery adoption in France today?

00:18
Dr. Martin: Adoption is growing, but it is still concentrated in larger academic hospitals.
"""


class TestParser(unittest.TestCase):
    def setUp(self):
        self.test_file = "tests/_sample_transcript.txt"
        with open(self.test_file, "w", encoding="utf-8") as f:
            f.write(SAMPLE_TRANSCRIPT)
        self.transcript = parse_transcript(self.test_file)

    def tearDown(self):
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

    def test_header_parsed_correctly(self):
        self.assertEqual(self.transcript.expert_name, "Dr. Jean Martin")
        self.assertEqual(self.transcript.role, "Head of Urology")
        self.assertEqual(self.transcript.market, "France")

    def test_segments_parsed(self):
        self.assertEqual(len(self.transcript.segments), 2)
        self.assertEqual(self.transcript.segments[0].timestamp, "00:00")
        self.assertEqual(self.transcript.segments[1].timestamp, "00:18")
        self.assertIn("Dr. Martin", self.transcript.segments[1].speaker)

    def test_verify_quote_true_for_real_quote(self):
        quote = "Adoption is growing, but it is still concentrated in larger academic hospitals."
        self.assertTrue(verify_quote(quote, self.transcript.raw_text))

    def test_verify_quote_false_for_fake_quote(self):
        quote = "This sentence does not exist in the transcript at all."
        self.assertFalse(verify_quote(quote, self.transcript.raw_text))

    def test_find_segment_for_quote(self):
        quote = "concentrated in larger academic hospitals"
        segment = find_segment_for_quote(self.transcript, quote)
        self.assertIsNotNone(segment)
        self.assertEqual(segment.timestamp, "00:18")

    def test_verify_quote_and_timestamp_correct(self):
        quote = "Adoption is growing, but it is still concentrated in larger academic hospitals."
        checks = verify_quote_and_timestamp(quote, "00:18", self.transcript)
        self.assertTrue(checks["quote_verified"])
        self.assertTrue(checks["timestamp_verified"])

    def test_verify_quote_and_timestamp_wrong_timestamp(self):
        quote = "Adoption is growing, but it is still concentrated in larger academic hospitals."
        checks = verify_quote_and_timestamp(quote, "00:00", self.transcript)
        self.assertTrue(checks["quote_verified"])
        self.assertFalse(checks["timestamp_verified"])
        self.assertEqual(checks["actual_timestamp"], "00:18")


if __name__ == "__main__":
    unittest.main()