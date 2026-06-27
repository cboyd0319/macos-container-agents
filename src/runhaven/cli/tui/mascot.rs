//! The RunHaven mascot: a small "cube buddy", a friendly glass container cube
//! with a tiny agent spark inside, drawn as Unicode half-block pixel art so it
//! works in any terminal without image protocols. Branding only; it shares no
//! data plumbing with the functional screens (see docs/plans/tui-architecture.md).
//!
//! Each `SPRITE` row is one pixel row of palette keys (a space is transparent).
//! `lines` pairs two pixel rows into one text row using the upper-half-block
//! glyph, so the foreground colors the top pixel and the background the bottom.

use ratatui::style::{Color, Style};
use ratatui::text::{Line, Span};

const WIDTH: usize = 16;

/// Pixel rows. Width and even-row-count are enforced by a test.
const SPRITE: &[&str] = &[
    "  oooooooooooo  ",
    "  offffffffffo  ",
    "  ofccccccccfo  ",
    "  occcccccccco  ",
    "  oceecccceeco  ",
    "  oceecccceeco  ",
    "  occcccccccco  ",
    "  occeccccecco  ",
    "  occceeeeccco  ",
    "  occccsscccco  ",
    "  occccsscccco  ",
    "  occcccccccco  ",
    "  oooooooooooo  ",
    "    LL    LL    ",
    "    LL    LL    ",
    "  111111111111  ",
    " 22222222222222 ",
    "3333333333333333",
];

fn palette(key: u8) -> Option<Color> {
    match key {
        b'o' => Some(Color::Rgb(46, 111, 207)),  // deep-blue edge
        b'f' => Some(Color::Rgb(205, 232, 255)), // frost highlight
        b'c' => Some(Color::Rgb(91, 211, 221)),  // cyan glass
        b'e' => Some(Color::Rgb(14, 32, 54)),    // eye
        b's' => Some(Color::Rgb(255, 210, 74)),  // agent spark (gold)
        b'L' => Some(Color::Rgb(62, 155, 242)),  // legs
        b'1' => Some(Color::Rgb(62, 155, 242)),  // base, blue
        b'2' => Some(Color::Rgb(63, 198, 206)),  // base, teal
        b'3' => Some(Color::Rgb(70, 224, 166)),  // base, mint
        _ => None,                               // space or unknown: transparent
    }
}

fn pixel(row: usize, col: usize) -> Option<Color> {
    SPRITE
        .get(row)
        .and_then(|line| line.as_bytes().get(col))
        .copied()
        .and_then(palette)
}

/// The mascot rendered as half-block text lines.
pub fn lines() -> Vec<Line<'static>> {
    let mut lines = Vec::with_capacity(SPRITE.len() / 2);
    let mut row = 0;
    while row + 1 < SPRITE.len() {
        let mut spans = Vec::with_capacity(WIDTH);
        for col in 0..WIDTH {
            let (symbol, style) = match (pixel(row, col), pixel(row + 1, col)) {
                (None, None) => (" ", Style::default()),
                (Some(top), None) => ("\u{2580}", Style::default().fg(top)),
                (None, Some(bottom)) => ("\u{2584}", Style::default().fg(bottom)),
                (Some(top), Some(bottom)) => ("\u{2580}", Style::default().fg(top).bg(bottom)),
            };
            spans.push(Span::styled(symbol, style));
        }
        lines.push(Line::from(spans));
        row += 2;
    }
    lines
}

/// Width in terminal cells.
pub const CELL_WIDTH: u16 = WIDTH as u16;

/// Height in terminal cells (two pixel rows per cell).
pub fn cell_height() -> u16 {
    (SPRITE.len() / 2) as u16
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sprite_rows_are_uniform_and_even() {
        assert_eq!(SPRITE.len() % 2, 0, "need an even pixel-row count");
        for (i, row) in SPRITE.iter().enumerate() {
            assert_eq!(
                row.chars().count(),
                WIDTH,
                "row {i} is the wrong width: {row:?}"
            );
        }
    }

    #[test]
    fn lines_match_cell_height_and_width() {
        let lines = lines();
        assert_eq!(lines.len() as u16, cell_height());
        for line in &lines {
            assert_eq!(line.spans.len(), WIDTH);
        }
    }
}
