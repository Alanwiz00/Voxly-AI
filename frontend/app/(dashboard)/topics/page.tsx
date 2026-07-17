import { redirect } from "next/navigation";

export default function TopicsRedirect() {
  redirect("/settings?tab=topics");
}
