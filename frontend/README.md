This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

### Demo with two accounts

Keep `npm run dev` running on port 3000. In another terminal, from `frontend`, run:

```bash
npm run dev:second
```

This starts port 3001 using a separate `.next-second` output directory, avoiding
Next.js's development-server lock conflict. Both servers reflect source edits.
The backend must also be running on port 8000; its CORS and CSRF trusted origins
must include both `http://localhost:3000` and `http://localhost:3001`.

Open `http://localhost:3000` in a normal browser window and
`http://localhost:3001` in an incognito/private window or a different browser.
Log into a different account in each window. Authentication uses cookies, which
are shared across localhost ports within the same browser profile, so separate
ports alone do not isolate accounts. Two private windows can also share cookies.

For a simpler demo, you can use those separate browser sessions with just the
existing server on port 3000.

For a third account, run `npm run dev:third` in another terminal from `frontend`.
It uses port 3002 and a separate `.next-third` output directory. The backend
allows port 3002 in its CORS and CSRF settings as well. Open
`http://localhost:3002` in another browser or a separate browser profile so its
login stays independent of the normal and private windows already in use.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
