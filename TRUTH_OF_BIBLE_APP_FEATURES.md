# Truth of Bible — App Features & Navigation Map

A catalog of every user-facing option in the app, with a breadcrumb showing exactly where to tap to reach it. Compiled directly from the app's navigation code (`Navigator.push` destinations, bottom nav, drawer menu), not from assumptions — file references are given where useful for engineering follow-up.

Breadcrumb notation: `→` means "tap this next." `☰` is the hamburger/menu button that opens the side drawer.

---

## 1. Top-Level Structure

The app has a **5-tab bottom navigation bar**, present on every main tab except Profile's full-bleed layout:

| # | Tab | Icon | Opens |
|---|-----|------|-------|
| 1 | **Community** | people | Community hub screen |
| 2 | **Bible** | book | Pushes the full Bible Reader as its own screen (not an in-place tab body) |
| 3 | **Explore** (Home) | search | The app's home/dashboard — this is the default screen on login |
| 4 | **Rewards** | gift | Faith Points / rewards dashboard |
| 5 | **Profile** | person | Account/profile screen |

Every tab except Profile shares the same top app bar:
- **☰ menu** (left) → opens the side **Drawer** (Section 8)
- **Greeting text** ("Good morning, {name}") → tap it to jump to the **Profile** tab
- **🔔 notification bell** (right) → **Notifications** screen

---

## 2. Explore (Home) Tab

`Bottom Nav → Explore`

The landing screen after login. Sections top to bottom:

### 2.1 Category quick-chips
`Explore → [chip row]`
- **All** — no-op filter chip
- **Articles** → `Explore → Articles` (Blog list)
- **Prayer Request** → `Explore → Prayer Request` (Prayer Requests screen)
- **Course** → `Explore → Course` (My Courses list)
- **Topics** → `Explore → Topics` (All Topics screen)
- **People** → `Explore → People` (Community Feed)

### 2.2 Today's Verse card
`Explore → Today's Verse card` → opens the full Daily Verse screen

### 2.3 "Bible Essentials"
`Explore → Bible Essentials → …`
- **Bible Reading** — "Read the Bible by book or chapter" → opens the Bible Reader
- **Daily Verse** — "Encouragement for today" → Daily Verse screen
- **AI Explore** — "Ask AI about people, places, and topics" → AI Bible Discover screen
- **Bible Battle** — "Challenge real players 1v1" → Bible Battle home
- **Gospel Compare** — "Compare the four Gospels side by side" → Gospel Event list

### 2.4 "Study & Tools"
`Explore → Study & Tools → …`
- **Bible Notes** — create/manage personal notes
- **Dictionary** — Easton's Dictionary, full list
- **Biblical Words** — biblical words/names explorer
- **AI Explore** — same AI Discover screen as above

### 2.5 "Featured" carousel
`Explore → Featured → …`
- **Easton's Dictionary** card → full Dictionary list
- **Daily Devotional** card → full Devotionals list

### 2.6 "What's New"
`Explore → What's New → …` — latest Blog articles; tapping one opens the full article

### 2.7 Bookmarks / Topics / Explore Hub row
`Explore → (icons row)`
- **Bookmarks** → Bookmark Categories screen
- **Dictionary** → All Dictionary screen
- **Topics** → All Topics screen
- **Explore Hub** → Bible Explore Hub screen

### 2.8 Quiz preview row
`Explore → Quiz card → View Quiz` — jumps straight into a specific quiz's detail screen (see Section 6)

---

## 3. Community Tab

`Bottom Nav → Community`

- **Community Feed** → `Community → Community Feed`
- **Prayer Wall / Request** → `Community → Prayer Wall`
- **Discussion Forum** → `Community → Discussion Forum`
- **Testimonials** → `Community → Testimonials`
- **Manage Posts** → `Community → Manage Posts` (edit/delete your own posts & requests)
- Bottom scripture banner (Galatians 6:2) — decorative, no action

---

## 4. Bible Reader

Reached from **any** of: `Bottom Nav → Bible`, `Explore → Bible Essentials → Bible Reading`, `☰ Drawer → Spiritual → Bible Reading`, or tapping into any specific verse/quiz reference elsewhere in the app.

### 4.1 Top bar
`Bible Reader → (top icons)`
- **🔍 Search** → expands the in-page verse search panel (search text, From book / To book range, Search/Clear)
- **🔖 Bookmark** → Bookmark Categories screen
- **文A Translate** → Bible Translation / module download screen (download & manage Bible versions)

### 4.2 Bottom bar
`Bible Reader → (bottom icons)`
- **‹ / ›** — previous/next chapter
- **Book : Chapter : Verse label** — tap to open the book/chapter picker drawer
- **Version dropdown** (e.g. "KJV") — switch translation for the current reading
- **✨ AI icon** → AI Bible Discover screen
- **⚙ Settings icon** → opens the reading-preferences end-drawer (font size, Strong's numbers toggle, theme, etc. — see Section 9)

### 4.3 Verse actions
`Bible Reader → long-press a verse → …` — a popup with up to 4 actions (shown when the underlying data exists for that verse):
- **Cross Reference**
- **TSK** (Treasury of Scripture Knowledge)
- **Compare** (side-by-side version comparison)
- **AI Explanation**

---

## 5. Rewards Tab

`Bottom Nav → Rewards`

- **Wallet balance card** → `Rewards → Wallet`
- **Points/streak card** → `Rewards → Reward History`
- **Read & Earn** → `Rewards → Read & Earn` (earn points by reading/studying)
- **Blessings** → `Rewards → Blessings` (redeem points in the rewards shop)
- **Invite Friends** → `Rewards → Invite Friends` (Refer & Earn)
- **Faith Journey** → `Rewards → Faith Journey` (points/activity history)
- **Daily Prayer** → `Rewards → Daily Prayer` (daily check-in for points)
- **My Blessings** → `Rewards → My Blessings` (your redemption order history)

---

## 6. Quiz

Reached via `☰ Drawer → Spiritual → Quiz`, or `Explore → Quiz card`.

- **Quiz List** — search, sort, and filter (Quiz Type / Negative Marking / Shuffled) all available quizzes
  `Quiz List → 🔍 search` · `Quiz List → ⇅ sort` · `Quiz List → ⚙ filter`
- **Quiz Detail** → `Quiz List → tap a quiz` — shows marks, passing score, attempts, time limit, quiz settings, and past submission history
  - `Quiz Detail → Display Settings` → text-size/appearance settings
  - `Quiz Detail → Leaderboard` → this quiz's rank list
  - `Quiz Detail → Submission History → an attempt` → that attempt's score screen
  - `Quiz Detail → Start Quiz` → confirmation sheet → begins the quiz
- **Quiz Play** — question, answer options, progress dots, timer (if the quiz has one), Back/Next
  `Quiz Play → Show all` → full question-navigator grid → `Exit From Quiz` (with confirmation) or jump to any question
- **Submit** → confirmation dialog → **Submitted Successfully** screen → `View Score`
- **Score / Result** → correct/wrong counts, percentage, your score
  `Score → Share` (share the app) · `Score → Exit` (back to start) · `Score → Compare` (answer review, if the quiz allows it) · `Score → feedback box → Send` (raises a support ticket about this quiz)
- **Compare / Answer Review** → question-by-question correct vs. your answer, with a "Show all" question-navigator grid of its own

---

## 7. Profile Tab

`Bottom Nav → Profile`

Quick-actions grid:
- **Transactions** → Wallet screen
- **Rewards** → jumps to the Rewards tab
- **Refer** → Refer & Earn screen
- **Prayer** → Prayer Requests
- **Saved** → Bookmark Categories
- **Community** → jumps to the Community tab
- **Settings** → `Profile → Settings` (see Section 9)
- **Support** → `Profile → Support` (Help Desk, see Section 10)

Plus: recent activity list (tapping an entry deep-links back into whatever it refers to — a quiz, a verse, etc.), and reward/points summary cards linking to Reward History / Wallet.

---

## 8. Side Drawer (☰)

Opened from the menu icon in the top app bar on Community/Explore/Rewards. Sections, in order:

**Admin** *(only visible to Batch Evaluator / Moderator / Course Creator roles)*
- Admin Panel → SaaS admin dashboard

**Spiritual**
- Daily Verse
- Bible Reading → Bible Reader
- Bible Translation → module download/selection screen
- AI Explore → AI Bible Discover screen
- Devotions → full Devotionals list
- Prayer Requests
- Courses → My Courses list
- Moments of Ministry → photo/media gallery
- Quiz → Quiz List (Section 6)
- Certificates → your earned certificates
- Batches → your enrolled batches
- Explore → jumps to the Explore tab
- Gospel Compare → Gospel Event list

**Rewards**
- Rewards → jumps to the Rewards tab
- Reward History
- Referral Program → Refer & Earn
- Referral Tier → tier list/benefits
- Earn Points
- Redeem Points → (Reward History)

**Community**
- Community Feed
- Prayer Wall

**Wallet**
- Wallet
- History, Donation, Update Wallet *(all currently point to the same Wallet screen)*

**Account**
- My Profile → jumps to the Profile tab
- Notifications
- Settings (Section 9)
- Language → the Bible-Settings screen's Language tab
- Help & Support → Help Desk (Section 10)
- About Us

Below the sections: a **Dark Theme** toggle (also settable from Settings → Bible Settings → Appearance — both control the same app-wide setting), **Logout** (with confirmation), and the app version number.

---

## 9. Settings

`☰ Drawer → Account → Settings` or `Profile → Settings`

Six tiles:
- **Bible Settings** → a 4-tab screen:
  - *Bible Font* — verse text size/style for reading
  - *Question Font* — text size for quizzes
  - *Bible Language* — reading-language selection
  - *Appearance* — the three **global** appearance controls used across the whole app:
    - **Theme** (Light / Dark / other named themes)
    - **Text Size** (scales all app text)
    - **UI Size** (Compact / Comfortable / Spacious — controls button/card/spacing density everywhere)
- **Support Ticket** → Help Desk (Section 10)
- **How This App Works** → in-app instructions page
- **FAQ** → Frequently Asked Questions
- **About** → About This App
- **Privacy Policy**

The Bible Reader's own end-drawer (⚙ icon, Section 4.2) has a *narrower*, reading-specific settings panel (verse font size, Strong's numbers on/off, etc.) — separate from the global Appearance controls above, by design, so a Bible-reading font preference doesn't fight the app-wide Text Size setting.

---

## 10. Help Desk / Support

`☰ Drawer → Account → Help & Support`, `Profile → Support`, or `Settings → Support Ticket`

- **Ticket List** — search bar (combined with filter icon), tabs for open/your tickets
  `Support → 🔍+⚙ search/filter bar`
- **New Ticket** → floating action button (bottom-right) → ticket creation form
- **Ticket Detail** → tap any ticket → full conversation thread, status, reply box

---

## 11. Notifications

`🔔 bell icon` (top app bar) or `☰ Drawer → Account → Notifications` — a flat list of push/system notifications; tapping one deep-links to whatever it references.

---

## 12. Onboarding / Auth (pre-login)

- **Splash screen** → checks login state and app-version, then routes to either the intro/login flow or straight into the app
- **Introduction / Login** → sign in (Google or credentials) or continue as guest
- **WhatsApp OTP verification** → collects/verifies a phone number after first login
- **First-run Appearance setup** → shown once, on first login, before landing on Explore

---

## Notes for future maintenance

- Several drawer items intentionally point at the *same* destination screen today (`Wallet`/`History`/`Donation`/`Update Wallet`; `Redeem Points`/`Reward History`) — that's the current app behavior, not a documentation error.
- The **Bible** bottom-nav tab and several drawer items (`Explore`, `Rewards`, `My Profile`, `Community`) don't open a new sub-screen — they just switch which bottom-nav tab is active.
- This map reflects the codebase as of this session (`git log` on `darkmode-update`); if screens are added, removed, or re-routed, this file should be updated alongside that change rather than left to drift.
