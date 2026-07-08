import json
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.services import analytics_service


class AnalyticsServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.event_path = Path(self.temp_dir.name) / "workspace" / "analytics" / "events.jsonl"

    def tearDown(self):
        analytics_service.clear_events(self.event_path)
        self.temp_dir.cleanup()

    def test_track_event_creates_jsonl_file(self):
        event = analytics_service.track_event(
            "dataset_uploaded",
            properties={"row_count": 2, "column_count": 3},
            context={"project_id": "project-1", "dataset_id": "dataset-1", "dataset_type": "uploaded"},
            event_file_path=self.event_path,
        )

        self.assertTrue(self.event_path.is_file())
        lines = self.event_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        parsed = json.loads(lines[0])
        self.assertEqual(parsed["event_id"], event["event_id"])
        self.assertEqual(parsed["event_name"], "dataset_uploaded")

    def test_required_common_fields_exist(self):
        event = analytics_service.track_event("data_quality_viewed", event_file_path=self.event_path)

        for field in (
            "event_id",
            "event_name",
            "session_id",
            "timestamp",
            "success",
            "properties",
        ):
            self.assertIn(field, event)
        self.assertTrue(event["success"])
        self.assertEqual(event["properties"], {})

    def test_read_events_returns_written_events_with_limit(self):
        analytics_service.track_event("first_event", event_file_path=self.event_path)
        analytics_service.track_event("second_event", event_file_path=self.event_path)

        events = analytics_service.read_events(event_file_path=self.event_path)
        latest = analytics_service.read_events(limit=1, event_file_path=self.event_path)

        self.assertEqual([event["event_name"] for event in events], ["first_event", "second_event"])
        self.assertEqual(len(latest), 1)
        self.assertEqual(latest[0]["event_name"], "second_event")

    def test_clear_events_is_safe(self):
        analytics_service.track_event("report_export_clicked", event_file_path=self.event_path)

        analytics_service.clear_events(self.event_path)
        analytics_service.clear_events(self.event_path)

        self.assertFalse(self.event_path.exists())
        self.assertEqual(analytics_service.read_events(event_file_path=self.event_path), [])

    def test_missing_properties_and_context_do_not_crash(self):
        event = analytics_service.track_event(
            "cleaned_dataset_generated",
            properties=None,
            context=None,
            event_file_path=self.event_path,
        )

        self.assertIsNone(event["project_id"])
        self.assertIsNone(event["dataset_id"])
        self.assertIsNone(event["dataset_type"])
        self.assertEqual(event["properties"], {})

    def test_no_external_network_call_is_made(self):
        with patch.object(socket, "create_connection", side_effect=AssertionError("network call")):
            event = analytics_service.track_event(
                "missing_value_plan_added",
                properties={"missing_total": 3},
                event_file_path=self.event_path,
            )

        self.assertEqual(event["event_name"], "missing_value_plan_added")
        self.assertTrue(self.event_path.is_file())

    def test_private_like_property_values_are_redacted(self):
        event = analytics_service.track_event(
            "privacy_smoke",
            properties={"phone_number": "123456789", "row_count": 10},
            event_file_path=self.event_path,
        )

        self.assertEqual(event["properties"]["phone_number"], "[redacted]")
        self.assertEqual(event["properties"]["row_count"], 10)


if __name__ == "__main__":
    unittest.main()
