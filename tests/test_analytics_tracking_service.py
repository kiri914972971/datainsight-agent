import unittest

from src.services.analytics_tracking_service import (
    cleaned_dataset_properties,
    dataset_context,
    dataset_properties,
    safe_track_event,
    track_event_once,
)


class AnalyticsTrackingServiceTests(unittest.TestCase):
    def test_safe_track_event_swallows_tracker_failure(self):
        def failing_tracker(*args, **kwargs):
            raise OSError("disk unavailable")

        event = safe_track_event(
            "dataset_selected",
            properties={"row_count": 1},
            context={"project_id": "project-1"},
            tracker=failing_tracker,
        )

        self.assertIsNone(event)

    def test_track_event_once_uses_session_guard(self):
        calls = []

        def tracker(event_name, **kwargs):
            calls.append((event_name, kwargs))
            return {"event_name": event_name}

        state = {}

        first = track_event_once(
            state,
            "analytics_last_dataset_selected_project-1",
            "project-1:dataset-1",
            "dataset_selected",
            properties={"row_count": 2},
            context={"project_id": "project-1"},
            tracker=tracker,
        )
        second = track_event_once(
            state,
            "analytics_last_dataset_selected_project-1",
            "project-1:dataset-1",
            "dataset_selected",
            properties={"row_count": 2},
            context={"project_id": "project-1"},
            tracker=tracker,
        )

        self.assertEqual(first, {"event_name": "dataset_selected"})
        self.assertIsNone(second)
        self.assertEqual(len(calls), 1)

    def test_dataset_context_and_properties_are_aggregate_only(self):
        dataset = {
            "dataset_id": "dataset-1",
            "dataset_type": "uploaded",
            "row_count": 10,
            "column_count": 3,
        }

        self.assertEqual(
            dataset_context("project-1", dataset),
            {"project_id": "project-1", "dataset_id": "dataset-1", "dataset_type": "uploaded"},
        )
        self.assertEqual(
            dataset_properties(dataset),
            {"dataset_type": "uploaded", "row_count": 10, "column_count": 3},
        )

    def test_cleaned_dataset_properties_include_before_after_counts(self):
        properties = cleaned_dataset_properties(
            {
                "dataset_id": "cleaned_dataset",
                "source_dataset_id": "source-1",
                "source_dataset": {"dataset_type": "uploaded"},
                "before_rows": 5,
                "after_rows": 4,
                "before_columns": 3,
                "after_columns": 4,
            },
            missing_plan_step_count=2,
            duplicate_plan_enabled=True,
            id_override_count=1,
            outlier_plan_step_count=1,
        )

        self.assertEqual(properties["before_row_count"], 5)
        self.assertEqual(properties["after_row_count"], 4)
        self.assertEqual(properties["before_column_count"], 3)
        self.assertEqual(properties["after_column_count"], 4)
        self.assertEqual(properties["missing_plan_step_count"], 2)
        self.assertTrue(properties["duplicate_plan_enabled"])


if __name__ == "__main__":
    unittest.main()
