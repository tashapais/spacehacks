# PROJECT GOAL

NASA has performed decades of biological experiments in space, producing a massive collection of data and publications on how microgravity, radiation, and the space environment affect living systems. Although publicly available, this information can be difficult to explore or summarize effectively.

## Our Challenge

Build a dynamic AI-powered dashboard that leverages LLMs, knowledge graphs, and vectorized datasets to summarize NASA bioscience publications and enable interactive exploration of space biology research.

This tool aims to help scientists, mission planners, and the public:

- Quickly discover relevant studies and bioscience data
- Summarize experimental findings using AI
- Explore biological effects in microgravity through interactive visualization
- Enable future mission planning using lessons learned from previous NASA research

## CURRENT MVP (PHASE 1)

The current version sets up:

- A modern SvelteKit + TailwindCSS web app
- Linting and formatting using ESLint + Prettier
- A clean UI foundation for a chat-style interface similar to Perplexity’s layout
- Placeholder routes ready for connecting to an LLM/vectorized search backend

Backend connectivity (e.g., vector DB, Drizzle ORM, or API streaming) will be added later in development.

## PROJECT STRUCTURE

src/
├── lib/
│ ├── api/ → backend fetch helpers and integration
│ ├── components/ → reusable chat and UI components
│ ├── stores/ → global state management with Svelte stores
│ ├── utils/ → formatting and markdown parsing helpers
│ └── types/ → TypeScript interfaces and shared models
│
├── routes/
│ ├── +layout.svelte → app shell, navbar, global layout
│ ├── +page.svelte → main chat interface (MVP)
│ ├── api/query/ → mock LLM/AI route for testing chat UI
│ └── explore/ → reserved for future data exploration dashboard
│
├── app.css → Tailwind CSS base and utilities
└── static/ → logos and visual assets

## FUTURE DIRECTIONS

PHASE 2:
Integrate vectorized dataset and knowledge graph for intelligent search.

PHASE 3:
Add interactive dashboards to visualize experiment outcomes and correlations with missions.

PHASE 4:
Enable generative AI features to support future mission bio-planning and hypothesis generation.

## Developing

Once you've created a project and installed dependencies with `pnpm install`

```sh
pnpm run dev

# or start the server and open the app in a new browser tab
pnpm run dev -- --open
```

## Building

To create a production version of your app:

```sh
pnpm run build
```

You can preview the production build with `pnpm run preview`.

> To deploy your app, you may need to install an [adapter](https://svelte.dev/docs/kit/adapters) for your target environment.
