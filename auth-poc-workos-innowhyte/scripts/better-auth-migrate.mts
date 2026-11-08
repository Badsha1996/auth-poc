/**
 * Create or update Better Auth's own tables (user, session, account, verification, jwks).
 *
 *   npm run auth:migrate            apply
 *   npm run auth:migrate -- --sql   print the SQL only
 *
 * Runs against BETTER_AUTH_DATABASE_URL, never against DATABASE_URL: that database belongs to the
 * Python API (Alembic), and mixing Better Auth's tables into it would confuse Alembic and Prisma.
 */
import "dotenv/config";
import { getMigrations } from "better-auth/db/migration";
import { betterAuthOptions } from "../lib/auth/better-auth/server";

const authDb = process.env.BETTER_AUTH_DATABASE_URL?.trim();
if (authDb && authDb === process.env.DATABASE_URL?.trim()) {
  console.error(
    "BETTER_AUTH_DATABASE_URL is the same as DATABASE_URL. Give Better Auth its own database " +
      "(for example a second Neon database named 'auth').",
  );
  process.exit(1);
}

const options = betterAuthOptions();
try {
  const plan = await getMigrations(options);
  const changes = plan.toBeCreated.length + plan.toBeAdded.length + plan.toBeAddedIndexes.length;
  if (plan.schemaProblems.length) console.warn("Schema problems:\n- " + plan.schemaProblems.join("\n- "));

  if (changes === 0) {
    console.log("Better Auth tables are up to date.");
  } else if (process.argv.includes("--sql")) {
    console.log(await plan.compileMigrations());
  } else {
    console.log(`Creating: ${plan.toBeCreated.map((t) => t.table).join(", ") || "-"}`);
    console.log(`Adding columns to: ${plan.toBeAdded.map((t) => t.table).join(", ") || "-"}`);
    await plan.runMigrations();
    console.log("Better Auth migration complete.");
  }
} finally {
  await options.database.end();
}
