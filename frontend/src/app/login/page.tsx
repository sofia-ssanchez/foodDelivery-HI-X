
"use client";

import { useState } from "react";
import type { ComponentProps } from "react";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const router = useRouter();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [isError, setIsError] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit: NonNullable<ComponentProps<"form">["onSubmit"]> = async (event) => {
    event.preventDefault();

    setMessage("");
    setIsError(false);
    setIsLoading(true);

    try {
      const response = await fetch(
        "http://localhost:8000/api/accounts/login/",
        {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ username, password }),
        }
      );

      const data = await response.json();
      console.log("Login response:", data);

      if (!response.ok) {
        throw new Error(
          "Invalid username or password. Please try again."
        );
      }

      const destinations: Record<string, string> = {
        customer: "/dashboard/customer",
        restaurant: "/dashboard/restaurant",
        courier: "/dashboard/courier",
        operator: "/dashboard/operator",
      };

      const destination = destinations[data.role];

      if (!destination) {
        throw new Error("Your account has an unrecognized role.");
      }

      // Navigate only after Django confirms successful login.
      router.replace(destination);
    } catch (error) {
      setIsError(true);
      setMessage(
        error instanceof Error
          ? error.message
          : "Something went wrong. Please try again."
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="page-container botanical-background">
      <section className="botanical-card page-content grid grid-cols-1 md:grid-cols-2">
        <div className="brand-panel flex flex-col justify-between p-8 md:p-12">
          <div>
            <p className="text-4xl font-semibold uppercase tracking-[0.2em] brand-accent">
              Five Leaf Clover
            </p>

            <h1 className="text-4xl font-bold leading-tight tracking-tight md:text-2xl">
              Welcome back!
            </h1>

            <p className="mt-6 max-w-sm leading-7 text-white/75">
              Vegan food delivery made simple!
            </p>
          </div>

        </div>

        <div className="p-6 sm:p-10 md:p-12">
          <p className="eyebrow">It&apos;s good to see you</p>

          <h2 className="page-title mt-3">Log in</h2>

          <p className="body-text mt-3 mb-8">
            Enter your account details below.
          </p>

          <form onSubmit={handleSubmit} className="form-stack">
            <div className="form-field">
              <label className="form-label" htmlFor="username">
                Username
              </label>

              <input
                className="form-input"
                id="username"
                name="username"
                type="text"
                autoComplete="username"
                placeholder="Your username"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                required
              />
            </div>

            <div className="form-field">
              <label className="form-label" htmlFor="password">
                Password
              </label>

              <input
                className="form-input"
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                placeholder="Your password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </div>

            {message && (
              <div
                className={`message ${
                  isError ? "message-error" : "message-success"
                }`}
                role="status"
              >
                {message}
              </div>
            )}

            <button
              className="btn btn-primary btn-full"
              type="submit"
              disabled={isLoading}
            >
              {isLoading ? "Logging in..." : "Log in"}
            </button>
          </form>

          <p className="body-text mt-6 text-center">
            Don&apos;t have an account?{" "}
            <a href="/signup" className="font-semibold">
              Sign up
            </a>
          </p>
        </div>
      </section>
    </main>
  );
}
