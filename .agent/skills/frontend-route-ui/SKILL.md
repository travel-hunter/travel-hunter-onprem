name: frontend-route-ui
description: Use when changing Travel Hunter frontend routes, pages, components, or visual behavior.

# Goal

Maintain a production-quality responsive app while preserving the route and API boundaries.

# When To Use

- Adding or changing pages.
- Changing route protection or navigation.
- Changing app layout, cards, forms, CTA behavior, or responsive styles.
- Changing frontend data loading state.

# Rules

- Pages must access data through `src/api` boundaries.
- Do not import seed data directly into pages or reusable UI components.
- Keep anonymous protected-route redirect behavior.
- Do not reintroduce prototype wrappers, phone status bar text, or explanatory prototype copy.
- Preserve empty/loading/error states when adding async UI.
- Use existing design tokens and component patterns before adding new abstractions.

# Responsive Viewports

Check UI behavior at:

- 360 x 780
- 390 x 844
- 430 x 932
- 1024 x 768
- 1440 x 900

# Validation

Run as relevant:

```bash
npm run typecheck
npm test
npm run test:e2e
npm run build
```

# Acceptance Criteria

- No blank `#root`.
- No unintended horizontal overflow.
- Public and protected route smoke behavior still matches `docs/deployment-cicd/03-frontend-guide.md`.
- Text is readable and not clipped on mobile widths.
