
"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

const dashboardInfo: Record<
  string,
  { title: string }
> = {
  customer: {
    title: "Welcome, customer!",
  },
  restaurant: {
    title: "Restaurant dashboard",
  },
  courier: {
    title: "Courier dashboard",
  },
  operator: {
    title: "Operator dashboard",
  },
};

export default function DashboardPage() {
  const params = useParams<{ role: string }>();
  const role = params.role;
  const dashboard = dashboardInfo[role];

  if (!dashboard) {
    return (
      <main className="page-container botanical-background">
        <section className="form-card">
          <h1 className="section-title">Page not found</h1>
          <p className="body-text mt-3">
            This dashboard does not exist.
          </p>
          <Link className="btn btn-primary mt-6" href="/">
            Back to login
          </Link>
        </section>
      </main>
    );
  }

  return (
    <main className="page-container botanical-background">
      <section className="form-card">
        <p className="eyebrow">Five Leaf Clover</p>

        <h1 className="page-title mt-3">{dashboard.title}</h1>



        <p className="form-help mt-6">
          Signed-in role: {role}
        </p>

      </section>
    </main>
  );
}

