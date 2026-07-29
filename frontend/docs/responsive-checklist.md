# Responsive QA checklist (1280×720 split-screen)

Manual pass after Phase F responsive token work. Run with two snapped browser windows at **1280×720**.

## Shell

- [ ] Header tabs meet **≥40px** touch height; labels readable at **≥13px** effective body size
- [ ] Filter bar controls do not overlap when side-by-side with another window
- [ ] CVE feed cards remain readable without horizontal scroll

## Detail drawer

- [ ] Tab row scrolls horizontally; each tab **≥40px** tall
- [ ] Overview body text uses shell body token (no sub-12px primary copy)

## IOC Lookup

- [ ] Search input + CLEAR/LOOKUP actions on one row (stack on narrow)
- [ ] Lookup/Clear buttons **≥44px** min height
- [ ] Quota panel body text uses `--shell-font-body`

## Admin

- [ ] Status bar pills readable; metering/config labels use shell label token
- [ ] API keys metering table columns align at 1280px width

## Wallboard kiosk

- [ ] Tile labels and meta text remain legible at 1280×720
- [ ] Page control buttons meet min touch target

## Regression

- [ ] `./scripts/verify-local.sh` green (full local merge gate)
- [ ] `npm run test:unit` green
- [ ] `npm run build` green
