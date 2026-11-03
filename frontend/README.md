# MIRRAGE frontend revamped

Standalone React/Vite frontend for the refreshed public MIRRAGE experience. It intentionally lives beside the existing `frontend/` app and does not import from it.

## Run locally

```bash
npm install
npm run dev
```

The Vite dev server uses port `4174` by default.

## Checks

```bash
npm run build
npm run lint
npm run test:visuals
```

Use Node 22.13+ for the visual geometry tests. All account, VPN, session, and challenge actions remain frontend-only simulations.

## Authentication and workflows

Authentication uses the configured API service; no development login or credentials are bundled in the frontend. Challenge progress, VPN state, sessions, profile edits, settings, and theme preferences use the app's configured services and browser state where applicable.

Available routes include `/login`, `/register`, `/verify-otp`, `/forgot-password`, `/reset-password`, `/dashboard`, `/vpn`, `/challenges`, `/challenges/:id`, `/sessions`, `/profile`, and `/settings`.

## Design Studio

The `Explore Designs` / `Design Studio` control is available on the public surface and in the authenticated workspace. It provides 18 starting presets, live search and category filters, favorites, recent designs, side-by-side comparisons, previous/next navigation, random combinations, custom preset saving, motion intensity, an independent 3D-effects switch, and a Logo Lab with Signal Core, Cyber Grid, Egyptian Eye, Critical Signal, and Cipher Orbit marks. Static and dynamic logo choices persist locally and update the interface wordmark plus browser favicon.

The selected preset, favorites, recent designs, custom presets, animation preference, and 3D preference are stored under separate `mirrage-design-*` browser keys so visual exploration never resets account, challenge, VPN, or session state.

The dashboard contains an interactive simulated 3D network topology: drag to rotate, use the controls to zoom/reset, select nodes, hover for IP/status details, and toggle between `3D` and `2D`. The public hero contains a separate pointer-responsive signal core. Both are mock visualizations and do not scan networks or execute commands.

## Spatial visuals and open layouts

- **Landing:** one large, unboxed signal core, concise navigation, a single primary action, and open sections. Removed the repeating ticker, invented live counts, invitation scarcity, redundant promo panels, and duplicate calls to action.
- **Dashboard:** inline statistics, one suggested target, a spacious topology view, and compact session/activity summaries. VPN, sessions, challenges, and other workflows remain accessible.
- **Core:** perspective-projected torus/sphere wireframes and orbital particles. Drag or use arrow keys to rotate; activate to expand; pause/resume and reset are separate controls.
- **Network:** depth-sorted nodes and moving packets, proper incident-link highlighting, mouse/touch hit testing, keyboard node inspection, zoom, and flat/spatial modes.

The renderer uses procedural 3D coordinates projected onto a transparent Canvas 2D surface; it needs no WebGL or additional runtime library. Frame rate, geometry density, and backing resolution are bounded. Automatic drawing stops offscreen and in hidden tabs. Reduced-motion, zero intensity, and disabled 3D settings are respected; canvas failure falls back to a static SVG with usable controls.

### Verification and manual smoke steps

`npm run test:visuals` covers flat versus perspective projection, edge alignment, incident-link selection, and depth-aware hit testing (five tests).

1. Open `/`, rotate and activate the core, then pause and reset it.
2. Open **Explore Designs**, select a preset, switch light/dark, and reload. The design should persist.
3. Enable reduced motion or disable 3D in the studio. Automatic motion should stop; node inspection remains usable.
4. Sign in through the configured authentication flow. Inspect a node in `/dashboard`, zoom, reset, and switch to 2D.
5. At 320px and desktop widths, check the landing menu, workspace navigation, and scene controls. Changing designs must leave the current account and progress intact.

Chromium checks were run for these interactions, responsive layouts, offscreen/hidden-tab suspension, and canvas fallback. Safari, Firefox, and physical low-powered hardware have not been verified.
