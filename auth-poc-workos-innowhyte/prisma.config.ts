// Prisma is a READ model here. The Python backend (mock-backend-innowhyte) owns the schema through
// Alembic migrations. Never run `prisma migrate` or `prisma db push` against this database.
// After a backend migration, run: npm run db:pull && npm run db:generate
import "dotenv/config";
import { defineConfig } from "prisma/config";

export default defineConfig({
  schema: "prisma/schema.prisma",
  datasource: {
    url: process.env["DATABASE_URL"],
  },
});
