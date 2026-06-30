use super::*;

#[test]
fn format_tokens_compact_matches_status_bridge_behavior() {
    assert_eq!(format_tokens_compact(-1), "0");
    assert_eq!(format_tokens_compact(999), "999");
    assert_eq!(format_tokens_compact(1_200), "1.2K");
    assert_eq!(format_tokens_compact(12_345_678), "12.3M");
}

#[test]
fn format_directory_display_honors_zero_width() {
    assert_eq!(
        format_directory_display(Path::new("/tmp/runhaven"), Some(0)),
        ""
    );
}
