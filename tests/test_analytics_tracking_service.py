import unittest

from src.services.analytics_tracking_service import (
    cleaned_dataset_properties,
    dataset_context,
    dataset_properties,
    event_counts_by_name,
    main_flow_funnel_rows,
    recent_events_table,
    safe_track_event,
    summarize_events,
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

    def test_summarize_events_returns_zero_summary_for_empty_list(self):
        self.assertEqual(
            summarize_events([]),
            {
                "total": 0,
                "success_count": 0,
                "failure_count": 0,
                "success_rate": 0.0,
                "latest_timestamp": None,
            },
        )

    def test_summarize_events_returns_counts_and_success_rate(self):
        summary = summarize_events(
            [
                {"event_name": "dataset_uploaded", "success": True, "timestamp": "2026-01-01T00:00:00Z"},
                {"event_name": "report_export_failed", "success": False, "timestamp": "2026-01-02T00:00:00Z"},
                {"event_name": "data_quality_viewed", "success": True, "timestamp": "2026-01-03T00:00:00Z"},
            ]
        )

        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["success_count"], 2)
        self.assertEqual(summary["failure_count"], 1)
        self.assertEqual(summary["success_rate"], 66.67)
        self.assertEqual(summary["latest_timestamp"], "2026-01-03T00:00:00Z")

    def test_event_counts_by_name_sorts_by_count_then_name(self):
        rows = event_counts_by_name(
            [
                {"event_name": "dataset_selected"},
                {"event_name": "dataset_uploaded"},
                {"event_name": "dataset_selected"},
            ]
        )

        self.assertEqual(
            rows,
            [
                {"event_name": "dataset_selected", "count": 2},
                {"event_name": "dataset_uploaded", "count": 1},
            ],
        )

    def test_recent_events_table_returns_latest_events_first(self):
        rows = recent_events_table(
            [
                {"timestamp": "1", "event_name": "old", "success": True},
                {
                    "timestamp": "2",
                    "event_name": "new",
                    "success": False,
                    "dataset_type": "uploaded",
                    "project_id": "project-1",
                    "duration_ms": 12,
                    "error_type": "export_error",
                },
            ],
            limit=1,
        )

        self.assertEqual(
            rows,
            [
                {
                    "timestamp": "2",
                    "event_name": "new",
                    "success": False,
                    "dataset_type": "uploaded",
                    "project_id": "project-1",
                    "duration_ms": 12,
                    "error_type": "export_error",
                }
            ],
        )

    def test_main_flow_funnel_rows_include_known_mvp_events(self):
        rows = main_flow_funnel_rows(
            [
                {"event_name": "dataset_uploaded"},
                {"event_name": "dataset_uploaded"},
                {"event_name": "report_export_success"},
            ]
        )
        by_event = {row["事件"]: row for row in rows}

        self.assertEqual(by_event["dataset_uploaded"]["次数"], 2)
        self.assertEqual(by_event["report_export_success"]["次数"], 1)
        self.assertEqual(by_event["report_export_failed"]["次数"], 0)


if __name__ == "__main__":
    unittest.main()
