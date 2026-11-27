"use client";

import { demoFetch } from "@/lib/demo-toasts";
import { useState } from "react";
import type { ComponentProps } from "react";
import { API_BASE } from "@/lib/api";

export default function SignupPage() {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("customer");
  const [restaurantName, setRestaurantName] = useState("");
  const [restaurantAddressQuery, setRestaurantAddressQuery] = useState("");
  const [restaurantAddresses, setRestaurantAddresses] = useState<{ address: string; token: string }[]>([]);
  const [restaurantAddressToken, setRestaurantAddressToken] = useState("");
  const [message, setMessage] = useState("");
  const [isError, setIsError] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const findRestaurantAddress = async () => {
    setMessage("");
    setIsError(false);
    setRestaurantAddresses([]);
    try {
      const response = await demoFetch(`${API_BASE}/api/restaurant/address-lookup/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ address: restaurantAddressQuery }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not find that address.");
      setRestaurantAddresses(data.results ?? []);
      if (!data.results?.length) setMessage("No matching Montreal address found.");
    } catch (error) {
      setIsError(true);
      setMessage(error instanceof Error ? error.message : "Could not find that address.");
    }
  };

  const handleSubmit: NonNullable<ComponentProps<"form">["onSubmit"]> = async (event) => {
    event.preventDefault();

    if (role === "restaurant" && !restaurantAddressToken) {
      setIsError(true);
      setMessage("Find and select your restaurant address.");
      return;
    }

    setMessage("");
    setIsError(false);
    setIsLoading(true);

    try {
      const response = await demoFetch(
        `${API_BASE}/api/accounts/signup/`,
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
            ...(role === "restaurant" ? { restaurant_name: restaurantName, restaurant_address_token: restaurantAddressToken } : {}),
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

            return `${details}`;
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
      setRestaurantName("");
      setRestaurantAddressQuery("");
      setRestaurantAddressToken("");
      setRestaurantAddresses([]);
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
                placeholder="At least 8 characters"
                minLength={8}
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
              </select>
            </div>

            {role === "restaurant" && (
              <fieldset className="form-field rounded-xl border border-[var(--color-border)] p-4">
                <legend className="form-label px-1">Restaurant details · locked after linking</legend>
                <label className="form-label" htmlFor="restaurant-name">Restaurant name</label>
                <input className="form-input" id="restaurant-name" name="restaurant_name" type="text" autoComplete="organization" maxLength={150} placeholder="Enter your restaurant name" value={restaurantName} onChange={(event) => setRestaurantName(event.target.value)} required />
                <label className="form-label mt-3 block" htmlFor="restaurant-address">Restaurant address</label>
                <div className="flex gap-2">
                  <input className="form-input" id="restaurant-address" type="text" maxLength={250} placeholder="Search a Montreal street address" value={restaurantAddressQuery} onChange={(event) => { setRestaurantAddressQuery(event.target.value); setRestaurantAddressToken(""); setRestaurantAddresses([]); }} required />
                  <button className="btn btn-secondary shrink-0" type="button" onClick={() => void findRestaurantAddress()} disabled={restaurantAddressQuery.trim().length < 5}>Find address</button>
                </div>
                {restaurantAddresses.length > 0 && <ul className="mt-2 space-y-2">{restaurantAddresses.map((result) => <li key={result.address}><button className="btn btn-secondary btn-full text-left" type="button" onClick={() => { setRestaurantAddressQuery(result.address); setRestaurantAddressToken(result.token); setRestaurantAddresses([]); }}>{result.address}</button></li>)}</ul>}
              </fieldset>
            )}

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
