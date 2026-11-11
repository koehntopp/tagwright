# ADR 0041: A wider inspector on wide screens

- **Status**: Accepted
- **Date**: 2026-11-12
- **Supersedes**: the inspector width of 600 px in [0030](0030-ui-layout-and-design-system-v2.md) and the 600 px right zone of the top bar in [0031](0031-top-bar-again.md), from a viewport width of 1600 px up

## Context

The track rows gained badges (channels, DR, lyrics) and the inspector's track list is the busiest part of the screen. The owner asked for about 20% more width.

## Decision

- The inspector and, above it, the top bar's right zone are **720 px** wide when the viewport is **1600 px or wider**, and stay **600 px** below that. At 1440 px the top bar has no room for 720 px (the filters, the Staging / Library switch and the search box need about 850 px) and the card board would drop from three columns to two.
- Nothing else changes: the zone and the inspector keep the same left border, so the line stays continuous.

## Consequences

- On a 1920 px screen the card board has 1200 px (still four columns of 240 px at 2 rem padding).
- A narrower window than 1600 px looks exactly as before.
