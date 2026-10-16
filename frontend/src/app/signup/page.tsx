"use client";

import { useState } from "react";
import type { ComponentProps } from "react";

export default function SignupPage() {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("customer");
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
        "http://localhost:8000/api/accounts/signup/",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            username,
            email,
            password,
            role,
          }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        const errors = Object.entries(data)
          .map(([field, error]) => {
            const details = Array.isArray(error)
              ? error.join(", ")
              : typeof error === "object"
                ? JSON.stringify(error)
                : String(error);

            return `${field}: ${details}`;
          })
          .join(" ");

        throw new Error(errors || "Could not create your account.");
      }

      setMessage(
        "Your account was created successfully! You can now log in."
      );

      setUsername("");
      setEmail("");
      setPassword("");
      setRole("customer");
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
        {/* Left branding panel */}
        <div className="brand-panel flex flex-col justify-between p-8 md:p-12">
          <div>
            <p className="text-4xl font-semibold uppercase tracking-[0.2em] brand-accent">
              Five Leaf Clover
            </p>
            <br/>
            <p className="text-4xl font-bold leading-tight tracking-tight md:text-xl">
              Discover fresh plant-based meals from local restaurants around you!
            </p>
          </div>

        </div>

        {/* Signup form */}
        <div className="p-6 sm:p-10 md:p-12">
          <p className="eyebrow">Join now!</p>

          <h2 className="page-title mt-3">Create your account</h2>

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
                placeholder="Choose a username"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                required
              />
            </div>

            <div className="form-field">
              <label className="form-label" htmlFor="email">
                Email address
              </label>

              <input
                className="form-input"
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                placeholder="you@example.com"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
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
                autoComplete="new-password"
                placeholder="At least 6 characters"
                minLength={6}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </div>

            <div className="form-field">
              <label className="form-label" htmlFor="role">
                I want to join as a...
              </label>

              <select
                className="form-select"
                id="role"
                name="role"
                value={role}
                onChange={(event) => setRole(event.target.value)}
                required
              >
                <option value="customer">Customer</option>
                <option value="restaurant">Restaurant</option>
                <option value="courier">Courier</option>
                <option value="operator">Operator</option>
              </select>
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
              {isLoading ? "Creating account..." : "Create account"}
            </button>
          </form>

          <p className="body-text mt-6 text-center">
            Already have an account?{" "}
            <a href="/login" className="font-semibold">
              Log in
            </a>
          </p>
        </div>
      </section>
    </main>
  );
}
