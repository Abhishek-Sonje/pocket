---
name: Pocket
description: Shared expenses, clearly.
colors:
  page: "#f7f7f5"
  surface: "#ffffff"
  border: "#e6e5e0"
  field-border: "#d9d8d2"
  ink: "#1c1c1a"
  muted: "#6b6b66"
  accent: "#2f5d50"
  accent-hover: "#386b5c"
  gets-back: "#1f7a4d"
  gets-back-background: "#e8f4ec"
  owes: "#a2470f"
  owes-background: "#fbeee4"
  frost: "rgba(247,247,245,.92)"
avatars:
  green: ["#e8efe9", "#2f5d50"]
  violet: ["#efe9f5", "#5b4a8a"]
  blue: ["#e9eff7", "#33567f"]
  peach: ["#f7ece4", "#8a4a1f"]
  rose: ["#f5e9ee", "#8a3d58"]
  olive: ["#eef0e0", "#5d6320"]
typography:
  family: "DM Sans, system-ui, -apple-system, Segoe UI, sans-serif"
  source: "app/static/fonts/dm-sans-latin.woff2"
  license: "app/static/fonts/OFL.txt"
  helper: "13px"
  label: "13px"
  body: "14px"
  card-title: "16px"
  page-title: "22px"
  total: "36px"
  avatar-initials: "12px"
  line-height: 1.6
  title-line-height: 1.25
  title-tracking: "-0.025em"
  numeric-variant: tabular-nums
spacing:
  scale: ["4px", "8px", "12px", "16px", "20px", "24px", "32px", "40px", "48px"]
  card-padding: "32px"
  mobile-card-padding: "20px"
  card-gap: "20px"
layout:
  max-width: "760px"
  desktop-gutter: "24px"
  mobile-gutter: "16px"
  mobile-breakpoint: "560px"
  sticky-header-height: "72px"
  mobile-header-height: "64px"
elevation:
  surface: "0 1px 2px rgba(20,20,15,.04), 0 8px 24px rgba(20,20,15,.04)"
  header-blur: "16px"
shapes:
  card-radius: "14px"
  control-radius: "10px"
  inner-radius: "7px"
  avatar-radius: "50%"
  pill-radius: "999px"
components:
  control-height: "44px"
  utility-height: "36px"
  avatar-size: "32px"
  small-avatar-size: "24px"
  icon-size: "18px"
  focus-ring: "2px solid #2f5d50"
  focus-offset: "3px"
motion:
  control: "180ms"
  standard: "200ms"
  expand: "240ms"
  easing: ease-out
  press-offset: "1px"
---

## Overview

Pocket brings a calm, precise reading order to shared expenses. The page guides a reviewer through Goa Trip: add people, record Dinner, review suggested payments and explicitly record repayments. Generous whitespace, confident typography and consistent avatars make the details easy to scan.

The source of truth is app/static/style.css. Its root variables define color, type, spacing, sizing, corners, shadows and motion. The implementation is plain HTML, CSS and small vanilla JavaScript. All assets are local; there are no runtime CDN dependencies. A same-origin content policy prevents external asset and API requests.

## Colors

The light page is #f7f7f5. White cards have a 1px #e6e5e0 border; white fields have a #d9d8d2 border. Primary text is #1c1c1a, and helper text is #6b6b66. Deep green #2f5d50 marks primary actions, links and focus. Primary hover uses the slightly lighter #386b5c.

Financial states always include words. Gets back uses #1f7a4d on #e8f4ec, owes uses #a2470f on #fbeee4, and settled uses muted text on the page background. The hero pill says All settled up or the exact remaining rupee amount followed by left to settle.

Avatars select one of six fixed tint/text pairs using the integer user ID modulo six. Initials are decorative; the visible name remains alongside each avatar. Color never carries identity or financial status alone.

Checked contrast ratios include 4.99:1 for muted text on the page, 4.71:1 for gets back, 5.36:1 for owes, 7.49:1 for primary button labels and 6.13:1 for primary hover. Avatar pairs range from 5.56:1 to 6.53:1. Retain at least 4.5:1 for every text/background pair, including disabled labels and transient highlights.

## Typography

DM Sans is bundled as a variable WOFF2 in app/static/fonts, with its SIL Open Font License. It is served locally and uses font-display: swap. The system sans-serif stack is the fallback; there is no external font loading.

Helpers and labels are 13px, body text is 14px, card titles are 16px and page titles are 22px. Only Total spent uses the large 36px figure. Titles have -0.025em tracking and a 1.25 line height. Body line height is 1.6. Initials and step numbers use 12px.

Amounts use tabular-nums and show rupees with exactly two decimals. Existing integer and string conversions preserve precision. Long names and descriptions wrap. Amounts in the member table stay together and can scroll within the table region.

## Layout

One centered column has a maximum width of 760px, with 24px desktop gutters. Cards have 32px padding and 20px gaps. At 560px and below, gutters become 16px, card padding becomes 20px, and paired fields and inline forms stack.

Home shows simple group rows, a friendly illustrated empty state and an inline New group field. Each group row has a quiet pocket icon and a directional arrow.

An open group starts with a slim sticky header containing a back action, the current group name and a group switcher. A translucent page-colored background with a 16px blur keeps the header legible. The main content follows this order:

1. A hero card with the group name, Total spent and a labeled remaining-status pill.
2. People, with avatar chips, one Add person box and an existing-user dropdown.
3. Add an expense, with description, rupee amount, payer, participant chips, Everyone and a collapsed Advanced recorder field.
4. Who pays whom, with suggested payment routes, explicit inline recording, the member table and a secondary Record a different payment disclosure.
5. Activity, with a segmented Expenses / Repayments selector and the latest 50 entries of each type, newest first.

A skeleton replaces group content while data loads. Failed loads show a retry action and hide the financial summary so a previous group's totals cannot appear under the new name. Navigation responses are guarded against stale updates.

## Elevation

Cards and the toast share one very soft shadow token: 0 1px 2px rgba(20,20,15,.04), 0 8px 24px rgba(20,20,15,.04). Thin borders provide definition. Rows inside a card use dividers, without additional floating surfaces.

The header's restrained frosted material supports scrolling and wayfinding. No other decorative blur or elevated overlay is used.

## Shapes

Cards have 14px corners. Inputs, buttons, the activity selector and toast have 10px corners. Small inner surfaces use 7px corners. Avatars are circles, while member, participant and status chips use pill corners.

Standard controls have a 44px minimum height. Compact utility actions, disclosure headings and activity choices have a 36px minimum height. Main avatars are 32px; participant and narrow-screen payment avatars are 24px.

## Components

- Primary buttons are solid green with white text. Secondary buttons are white with a subtle border. Every interactive element has a visible focus ring. Disabled controls remain legible and submitting controls say Saving....
- Member chips combine initials and a name. Duplicate names include (#id) only when duplicates occur in the relevant list. User content is inserted as text.
- Add person creates a user and adds that user to the current group in one submission. Existing users are available through a separate dropdown.
- Participant chips contain native checkboxes and avatars. All members start selected, Everyone selects all, and saving is blocked when none are selected. The recorder lives under Advanced and defaults to the payer.
- Suggested payment rows show sender and recipient avatars, an arrow and an exact amount. Mark as paid expands a rupee input with Save and Cancel. Expanding records nothing. Only Save records a repayment, and the sender is its default recorder.
- The balance table shows Person, Paid, Share and a labeled status chip. Names wrap and the table scrolls within its own focusable region.
- The all-settled state pairs a small check icon with explicit text. Activity empty states explain what will appear once entries are recorded.
- The activity selector uses aria-current and a sliding neutral indicator. Activity rows show the payer or sender avatar, an amount and small Entered by metadata.
- Success and errors appear in a live notification toast with a Dismiss control. Errors also appear beside the affected form. No notification implies that Pocket moves or verifies money.
- Skeleton placeholders cover initial group and balance loading. Unchanged financial retries retain the same request ID; new or edited submissions receive a new ID. Buttons are disabled while a write is pending. Successful writes refresh the hero, suggestions, member balances and both histories.
- Icons are a few hand-written inline SVG symbols: pocket, plus, arrow and check. There is no icon library or external sprite.

## Motion

Control color, border and press transitions use 180ms ease-out. A pressed enabled button shifts down by 1px. Primary hover lightens the green without reducing text contrast below 4.5:1.

The repayment editor expands and collapses with a 240ms grid-row transition. Collapsed editors are inert and hidden from assistive technology. Newly added member and activity rows receive a brief 240ms soft highlight. The activity indicator slides over 200ms. The toast enters with a 200ms fade and an 8px rise.

Skeletons are static, keeping loading calm. The prefers-reduced-motion rule disables all animations, transitions and smooth scrolling. Motion never delays or triggers a financial write.

## Do's and Don'ts

- Do keep the page focused on people, shared expenses and explicit repayment recording.
- Do use the shared CSS variables for the complete visual system.
- Do preserve exact money handling, labeled financial states and visible keyboard focus.
- Do use local assets and retain the bundled font license.
- Do keep names readable and content contained at narrow widths.
- Do record a suggested payment only after an explicit Save.
- Don't imply that Pocket makes, moves or verifies payments.
- Don't show internal field names, storage units or request identifiers in UI copy.
- Don't add charts, competing large metrics, extra accent colors or decorative interface chrome.
- Don't change financial behavior to support a visual effect.
- Don't use em dashes in this guide or UI copy.
