//! Pure pet animation-frame-selection (timing) logic.
//!
//! Derived from openai/codex (`codex-rs/tui/src/pets/ambient.rs`), licensed
//! under Apache-2.0, copyright 2025 OpenAI. Modified by RunHaven on 2026-06-26:
//! only the decoupled, side-effect-free frame-selection logic was extracted.
//! The upstream `AmbientPet` struct, `FrameRequester`/`schedule_frame_in`
//! scheduling, the `PetNotification` state machine, and everything touching
//! `crate::tui`, `crate::app_event`, or `ratatui::layout::Rect` were
//! intentionally excluded; RunHaven drives its own tick loop and run-state
//! mapping.
//!
//! The full license text is in `licenses/codex-Apache-2.0.txt` and the required
//! attribution notice is in `THIRD_PARTY_NOTICES.md` at the repo root.
//!
//! These functions operate only on `super::model::Animation` /
//! `super::model::AnimationFrame` and `std::time::Duration`.

use std::time::Duration;

use super::model::Animation;
#[cfg(test)]
use super::model::AnimationFrame;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) struct AnimationFrameTick {
    pub(crate) sprite_index: usize,
    pub(crate) delay: Option<Duration>,
}

pub(crate) fn current_animation_frame(
    animation: &Animation,
    elapsed: Duration,
) -> Option<AnimationFrameTick> {
    if animation.frames.len() <= 1 {
        return Some(AnimationFrameTick {
            sprite_index: animation.frames.first()?.sprite_index,
            delay: None,
        });
    }

    let elapsed_nanos = elapsed.as_nanos();
    if let Some(loop_start) = animation
        .loop_start
        .filter(|idx| *idx < animation.frames.len())
    {
        let total_nanos = animation.total_duration().as_nanos();
        let prefix_nanos = animation.frames[..loop_start]
            .iter()
            .map(|frame| frame.duration.as_nanos())
            .sum::<u128>();
        let loop_nanos = animation.frames[loop_start..]
            .iter()
            .map(|frame| frame.duration.as_nanos())
            .sum::<u128>();
        let effective_elapsed = if elapsed_nanos >= total_nanos && loop_nanos > 0 {
            prefix_nanos + elapsed_nanos.saturating_sub(prefix_nanos) % loop_nanos
        } else {
            elapsed_nanos
        };
        frame_at_elapsed(animation, effective_elapsed)
    } else if elapsed_nanos >= animation.total_duration().as_nanos() {
        Some(AnimationFrameTick {
            sprite_index: animation.frames.last()?.sprite_index,
            delay: None,
        })
    } else {
        frame_at_elapsed(animation, elapsed_nanos)
    }
}

fn frame_at_elapsed(animation: &Animation, elapsed_nanos: u128) -> Option<AnimationFrameTick> {
    let mut remaining_elapsed = elapsed_nanos;
    for frame in &animation.frames {
        let frame_nanos = frame.duration.as_nanos().max(/*other*/ 1);
        if remaining_elapsed < frame_nanos {
            return Some(AnimationFrameTick {
                sprite_index: frame.sprite_index,
                delay: Some(nanos_to_duration(frame_nanos - remaining_elapsed)),
            });
        }
        remaining_elapsed = remaining_elapsed.saturating_sub(frame_nanos);
    }

    Some(AnimationFrameTick {
        sprite_index: animation.frames.last()?.sprite_index,
        delay: None,
    })
}

fn nanos_to_duration(nanos: u128) -> Duration {
    Duration::from_nanos(nanos.min(u128::from(u64::MAX)) as u64)
}

#[cfg(test)]
fn test_animation() -> Animation {
    Animation {
        frames: vec![
            AnimationFrame {
                sprite_index: 0,
                duration: Duration::from_millis(/*millis*/ 10),
            },
            AnimationFrame {
                sprite_index: 1,
                duration: Duration::from_millis(/*millis*/ 10),
            },
        ],
        loop_start: Some(/*loop_start*/ 0),
        fallback: "idle".to_string(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn animation_frame_uses_per_frame_duration() {
        let animation = test_animation();

        assert_eq!(
            current_animation_frame(&animation, Duration::from_millis(/*millis*/ 15)),
            Some(AnimationFrameTick {
                sprite_index: 1,
                delay: Some(Duration::from_millis(/*millis*/ 5)),
            })
        );
    }
}
