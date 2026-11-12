# ADR 0026: The Ready filter returns to the top bar

- **Status**: Accepted (the label "Ready" is now "Incomplete": [0054](0054-album-status-and-steps-consolidated.md)) (the Ready filter is in the top bar again, [0031](0031-top-bar-again.md))
- **Date**: 2026-11-09
- **Supersedes**: the statement in [0022](0022-top-bar-instead-of-sidebar.md) that there is no Ready filter (the rest of 0022 stands)

## Context

The Ready box was dropped from the top bar when it ran out of room. With the full library (826 albums, about 65 Ready) the owner needs to list the blue albums, and the sort order by status is not a filter. The search field now shrinks, so there is room.

## Decision

- The navigation entries are **All albums**, **Needs input**, **Ready**, **Fixed**, each with a count. Ready lists albums with status `ready` ([0054](0054-album-status-and-steps-consolidated.md)): no blocking issue, fewer than 6 steps done.
- Styling is unchanged from the other entries ([0022](0022-top-bar-instead-of-sidebar.md)).
