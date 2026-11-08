import { redirect } from "next/navigation";
import { auth } from "@/lib/auth";

export async function GET() {
  redirect(await auth.getSignUpUrl());
}
