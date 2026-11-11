# TicketFlow interface system

## Direction

A bright, precise support workbench. White navigation and work surfaces sit on a very light cool-neutral canvas. Emerald identifies primary actions and current selection. Ink text and clear separators make long queues and policy evidence easy to scan. Avoid dark framing, decorative gradients, uppercase eyebrows and repeated large metric cards.

The user selected this light direction on 2026-11-11. This is an improvement of the existing ecommerce workflow, not a new product or new business claims.

## Typography and layout

Use the installed system sans family with Chinese fallbacks. UI/body text 14px, secondary/metadata 12–13px, page headings 26px and section headings 15–16px. Code and resource identifiers may use monospace; labels do not. Use tabular numerals for counts and amounts.

Use a 4px spacing foundation: 8px inside tight groups, 12–16px between controls, 20–24px inside sections, 28–32px between major areas. Sidebar approximately 232px, sticky top bar 68px. On narrower screens use a proper navigation drawer and single-column layouts; long tables scroll within their container or use ticket cards.

## Tokens

- Canvas: #f6f8fa; surface: #ffffff; subtle surface: #f8fafb.
- Primary text: #172b27; secondary text: #52635e; metadata: #64756f.
- Brand/action: #12745c; soft selection: #eaf5ef.
- Border: #e3e9e6; stronger interactive boundary: #b9c9c1.
- Success: #24724b; warning: #926415; danger: #b54848; info: #3c648a.
- Controls: radius 8px; work panels: radius 12px. Borders define panels; shadows are reserved for overlays.

Map all Element Plus theme color shades and control defaults from the same palette. Focus rings must be visible. Status labels include text and never rely on color alone.

## Interaction and motion

The focal motion is a shared selection surface moving between navigation destinations and queue filters. It communicates where the user is, rather than replaying an entrance every time the page loads. Route changes use a short opacity transition; overlays retain Element Plus focus/escape handling. Process status changes and newly available retrieval evidence receive bounded feedback.

Use motion-v with user reduced-motion preferences. Routine feedback 120–180ms; navigation/selection 180–240ms with quick deceleration or a restrained spring. Content begins visible. No infinite decorative animations, blanket card hover lifts or long sibling staggers.

## Business UI

The ticket queue prioritizes status navigation, search, visible priority and an obvious row action. The review drawer separates customer/order facts, evidence and editable reply. Draft, approved and sent states remain distinct. Knowledge publishing and workflow saving keep explicit action boundaries. Statistics display actual API values, and loading uses placeholders rather than false zeroes.

The global search palette supports permitted pages and existing tickets, with keyboard navigation and IME-safe shortcuts. It must not execute business mutations. Dirty workflow settings are identifiable before publication.

## Guidance provenance

UI UX Pro Max returned general enterprise/minimalist style and table/mobile recommendations, but its design-system queries fell back to a generic marketing-page pattern without a matching support product identity. That hero/CTA pattern and automatic blue palette are not adopted. This system is based on the user's light-workbench preference, actual TicketFlow screens, targeted Vue/UX guidance and Impeccable Operate-mode checks.
