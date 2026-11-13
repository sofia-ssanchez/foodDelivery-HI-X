
"use client";

import { useEffect, useMemo, useState } from "react";
import { API_BASE, apiFetch } from "@/lib/api";
import CustomerOrders from "./customer-orders";

type Restaurant = {
  id: number;
  name: string;
  status: "open" | "closed" | "paused";
};

type MenuItem = {
  id: number;
  name: string;
  description?: string;
  price: number | string;
  status: "available" | "sold_out";
};

type CartItem = MenuItem & {
  quantity: number;
};

type OrderResponse = {
  id?: number;
  status?: string;
  message?: string;
  detail?: string;
};

const RESTAURANTS_ENDPOINT = `${API_BASE}/api/restaurants/`;

const menuEndpoint = (restaurantId: number) =>
  `${API_BASE}/api/restaurants/${restaurantId}/menu/`;

const ORDERS_ENDPOINT = `${API_BASE}/api/orders/`;

export default function CustomerDashboard() {
  const [section, setSection] = useState<"browse" | "active" | "past">("browse");

  const [restaurants, setRestaurants] = useState<Restaurant[]>([]);
  const [selectedRestaurant, setSelectedRestaurant] =
    useState<Restaurant | null>(null);

  const [menuItems, setMenuItems] = useState<MenuItem[]>([]);
  const [cart, setCart] = useState<CartItem[]>([]);

  const [loadingRestaurants, setLoadingRestaurants] = useState(true);
  const [loadingMenu, setLoadingMenu] = useState(false);
  const [placingOrder, setPlacingOrder] = useState(false);

  const [restaurantError, setRestaurantError] = useState("");
  const [menuError, setMenuError] = useState("");
  const [orderError, setOrderError] = useState("");

  const [orderMessage, setOrderMessage] = useState("");
  const [orderStatus, setOrderStatus] = useState("");

  useEffect(() => {
    const loadRestaurants = async () => {
      setLoadingRestaurants(true);
      setRestaurantError("");

      try {
        const response = await apiFetch(RESTAURANTS_ENDPOINT, {
          method: "GET",
          credentials: "include",
        });

        if (!response.ok) {
          throw new Error("Could not load restaurants.");
        }

        const data = await response.json();

        setRestaurants(Array.isArray(data) ? data : data.results ?? []);
      } catch (error) {
        setRestaurantError(
          error instanceof Error
            ? error.message
            : "Could not load restaurants."
        );
      } finally {
        setLoadingRestaurants(false);
      }
    };

    loadRestaurants();
  }, []);

  const selectRestaurant = async (restaurant: Restaurant) => {
    if (restaurant.status !== "open") return;

    setSelectedRestaurant(restaurant);

    setMenuItems([]);
    setCart([]);

    setMenuError("");
    setOrderError("");
    setOrderMessage("");
    setOrderStatus("");

    setLoadingMenu(true);

    try {
      const response = await apiFetch(menuEndpoint(restaurant.id), {
        method: "GET",
        credentials: "include",
      });

      if (!response.ok) {
        throw new Error("Could not load this restaurant's menu.");
      }

      const data = await response.json();

      setMenuItems(Array.isArray(data) ? data : data.results ?? []);
    } catch (error) {
      setMenuError(
        error instanceof Error
          ? error.message
          : "Could not load this restaurant's menu."
      );
    } finally {
      setLoadingMenu(false);
    }
  };

  const addToCart = (item: MenuItem) => {
    if (item.status !== "available") return;
    if (selectedRestaurant?.status !== "open") return;

    setOrderError("");
    setOrderMessage("");

    setCart((currentCart) => {
      const existingItem = currentCart.find(
        (cartItem) => cartItem.id === item.id
      );

      if (existingItem) {
        return currentCart.map((cartItem) =>
          cartItem.id === item.id
            ? {
                ...cartItem,
                quantity: cartItem.quantity + 1,
              }
            : cartItem
        );
      }

      return [
        ...currentCart,
        {
          ...item,
          quantity: 1,
        },
      ];
    });
  };

  const increaseQuantity = (itemId: number) => {
    const menuItem = menuItems.find((item) => item.id === itemId);

    if (
      !menuItem ||
      menuItem.status !== "available" ||
      selectedRestaurant?.status !== "open"
    ) {
      return;
    }

    setCart((currentCart) =>
      currentCart.map((item) =>
        item.id === itemId
          ? {
              ...item,
              quantity: item.quantity + 1,
            }
          : item
      )
    );
  };

  const decreaseQuantity = (itemId: number) => {
    setCart((currentCart) =>
      currentCart
        .map((item) =>
          item.id === itemId
            ? {
                ...item,
                quantity: item.quantity - 1,
              }
            : item
        )
        .filter((item) => item.quantity > 0)
    );
  };

  const removeFromCart = (itemId: number) => {
    setCart((currentCart) =>
      currentCart.filter((item) => item.id !== itemId)
    );
  };

  const totalPrice = useMemo(() => {
    return cart.reduce(
      (total, item) => total + Number(item.price) * item.quantity,
      0
    );
  }, [cart]);

  const placeOrder = async () => {
    setOrderError("");
    setOrderMessage("");
    setOrderStatus("");

    if (!selectedRestaurant) {
      setOrderError("Please select a restaurant first.");
      return;
    }

    if (selectedRestaurant.status !== "open") {
      setOrderError("This restaurant is not currently open.");
      return;
    }

    if (cart.length === 0) {
      setOrderError("Your order is empty.");
      return;
    }

    if (
      cart.some(
        (cartItem) =>
          !menuItems.some(
            (menuItem) =>
              menuItem.id === cartItem.id &&
              menuItem.status === "available"
          )
      )
    ) {
      setOrderError(
        "One or more items are no longer available. Please update your order."
      );
      return;
    }

    setPlacingOrder(true);

    try {
      const orderBody = {
        restaurant_id: selectedRestaurant.id,
        items: cart.map((item) => ({
          menu_item_id: item.id,
          quantity: item.quantity,
        })),
      };

      const response = await apiFetch(ORDERS_ENDPOINT, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(orderBody),
      });

      const data: OrderResponse = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail ||
            data.message ||
            "The order could not be placed. Please check your order."
        );
      }

      setOrderMessage(
        data.message ||
          (data.id
            ? `Order #${data.id} was placed successfully.`
            : "Order placed successfully.")
      );

      setOrderStatus(data.status || "placed");
      setCart([]);
    } catch (error) {
      setOrderError(
        error instanceof Error
          ? error.message
          : "Something went wrong while placing the order."
      );
    } finally {
      setPlacingOrder(false);
    }
  };

  const restaurantStatusLabel = (status: Restaurant["status"]) => {
    switch (status) {
      case "open":
        return "Open";
      case "closed":
        return "Closed";
      case "paused":
        return "Paused";
    }
  };

  const menuStatusLabel = (status: MenuItem["status"]) => {
    return status === "available" ? "Available" : "Sold Out";
  };

  return (
    <main
      className="page-container botanical-background"
      style={{ alignItems: "flex-start" }}
    >
      <section className="w-full max-w-[1600px] mx-auto">
        {/* Header */}
        <header className="mb-8">
          <p className="eyebrow">Five Leaf Clover</p>

          <h1 className="page-title mt-3">
            Customer Dashboard
          </h1>
        </header>

        <div className="grid grid-cols-1 md:grid-cols-[200px_minmax(0,1fr)] gap-6 items-start">
          <nav
            aria-label="Customer dashboard"
            className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 flex flex-col gap-3 md:sticky md:top-5"
          >
            <p className="eyebrow px-2 mb-2">Your account</p>

            {(
              [
                { key: "browse", label: "Order food" },
                { key: "active", label: "Active orders" },
                { key: "past", label: "Past orders" },
              ] as const
            ).map((item) => (
              <button
                key={item.key}
                type="button"
                aria-pressed={section === item.key}
                className={`btn btn-full ${
                  section === item.key ? "btn-primary" : "btn-secondary"
                }`}
                onClick={() => setSection(item.key)}
              >
                <span className="w-full text-left">{item.label}</span>
              </button>
            ))}
          </nav>

          <div className="min-w-0">
            {section !== "browse" && (
              <CustomerOrders category={section} />
            )}

            {section === "browse" && (
              <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
                {/* Restaurants */}
                <section className="form-card">
                  <h2 className="section-title">Restaurants</h2>

                  <p className="body-text mt-2">
                    Choose an open restaurant to view its menu.
                  </p>

                  {loadingRestaurants && (
                    <p className="body-text mt-4">
                      Loading restaurants...
                    </p>
                  )}

                  {restaurantError && (
                    <div className="message message-error mt-4">
                      {restaurantError}
                    </div>
                  )}

                  {!loadingRestaurants &&
                    !restaurantError &&
                    restaurants.length === 0 && (
                      <p className="body-text mt-4">
                        No restaurants are currently available.
                      </p>
                    )}

                  <div className="mt-4 flex flex-col gap-3">
                    {restaurants.map((restaurant) => {
                      const isSelected =
                        selectedRestaurant?.id === restaurant.id;

                      const isOpen = restaurant.status === "open";

                      return (
                        <button
                          key={restaurant.id}
                          type="button"
                          disabled={!isOpen}
                          className={`btn btn-full ${
                            isSelected
                              ? "btn-primary"
                              : "btn-secondary"
                          } disabled:opacity-50 disabled:cursor-not-allowed`}
                          onClick={() => selectRestaurant(restaurant)}
                        >
                          <span className="flex w-full items-center justify-between gap-2">
                            <span className="text-left">
                              {restaurant.name}
                            </span>

                            <span
                              className={`text-xs font-semibold px-2 py-1 rounded-full whitespace-nowrap ${
                                restaurant.status === "open"
                                  ? "bg-green-100 text-green-800"
                                  : restaurant.status === "paused"
                                  ? "bg-yellow-100 text-yellow-800"
                                  : "bg-red-100 text-red-800"
                              }`}
                            >
                              {restaurantStatusLabel(restaurant.status)}
                            </span>
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </section>

                {/* Menu */}
                <section className="form-card">
                  <h2 className="section-title">Menu</h2>

                  {!selectedRestaurant && (
                    <p className="body-text mt-3">
                      Select an open restaurant to view its menu.
                    </p>
                  )}

                  {selectedRestaurant && (
                    <>
                      <p className="body-text mt-3">
                        Menu for{" "}
                        <strong>{selectedRestaurant.name}</strong>
                      </p>

                      {loadingMenu && (
                        <p className="body-text mt-4">
                          Loading menu...
                        </p>
                      )}

                      {menuError && (
                        <div className="message message-error mt-4">
                          {menuError}
                        </div>
                      )}

                      {!loadingMenu &&
                        !menuError &&
                        menuItems.length === 0 && (
                          <p className="body-text mt-4">
                            This restaurant currently has no menu items.
                          </p>
                        )}

                      <div className="mt-5 flex flex-col gap-4">
                        {menuItems.map((item) => {
                          const isAvailable =
                            item.status === "available";

                          return (
                            <article
                              key={item.id}
                              className={`rounded-xl border p-4 ${
                                !isAvailable
                                  ? "opacity-60"
                                  : ""
                              }`}
                            >
                              <div className="flex items-start justify-between gap-2">
                                <h3 className="font-semibold">
                                  {item.name}
                                </h3>

                                <span
                                  className={`text-xs font-semibold px-2 py-1 rounded-full whitespace-nowrap ${
                                    isAvailable
                                      ? "bg-green-100 text-green-800"
                                      : "bg-red-100 text-red-800"
                                  }`}
                                >
                                  {menuStatusLabel(item.status)}
                                </span>
                              </div>

                              {item.description && (
                                <p className="body-text mt-2">
                                  {item.description}
                                </p>
                              )}

                              <p className="mt-3 font-semibold">
                                ${Number(item.price).toFixed(2)}
                              </p>

                              <button
                                type="button"
                                className="btn btn-primary btn-full mt-4 disabled:opacity-50 disabled:cursor-not-allowed"
                                disabled={!isAvailable}
                                onClick={() => addToCart(item)}
                              >
                                {isAvailable
                                  ? "Add to Order"
                                  : "Sold Out"}
                              </button>
                            </article>
                          );
                        })}
                      </div>
                    </>
                  )}
                </section>

                {/* Order */}
                <section className="form-card">
                  <h2 className="section-title">Your Order</h2>

                  {!selectedRestaurant && (
                    <p className="body-text mt-3">
                      Choose a restaurant to begin your order.
                    </p>
                  )}

                  {selectedRestaurant && cart.length === 0 && (
                    <p className="body-text mt-3">
                      Your order is empty.
                    </p>
                  )}

                  <div className="mt-4 flex flex-col gap-4">
                    {cart.map((item) => (
                      <article
                        key={item.id}
                        className="rounded-xl border p-4"
                      >
                        <div>
                          <h3 className="font-semibold">
                            {item.name}
                          </h3>

                          <p className="body-text mt-1">
                            ${Number(item.price).toFixed(2)} each
                          </p>
                        </div>

                        <div className="mt-4 flex items-center gap-3">
                          <button
                            type="button"
                            className="btn"
                            onClick={() => decreaseQuantity(item.id)}
                          >
                            -
                          </button>

                          <span>{item.quantity}</span>

                          <button
                            type="button"
                            className="btn"
                            disabled={
                              item.status !== "available" ||
                              selectedRestaurant?.status !== "open"
                            }
                            onClick={() => increaseQuantity(item.id)}
                          >
                            +
                          </button>
                        </div>

                        <p className="mt-3 font-semibold">
                          Subtotal: $
                          {(
                            Number(item.price) * item.quantity
                          ).toFixed(2)}
                        </p>

                        <button
                          type="button"
                          className="btn btn-full mt-3"
                          onClick={() => removeFromCart(item.id)}
                        >
                          Remove
                        </button>
                      </article>
                    ))}
                  </div>

                  {cart.length > 0 && (
                    <>
                      <div className="mt-6 border-t pt-4">
                        <p className="font-semibold">
                          Total: ${totalPrice.toFixed(2)}
                        </p>
                      </div>

                      <button
                        type="button"
                        className="btn btn-primary btn-full mt-4"
                        onClick={placeOrder}
                        disabled={
                          placingOrder ||
                          selectedRestaurant?.status !== "open"
                        }
                      >
                        {placingOrder
                          ? "Placing order..."
                          : "Place Order"}
                      </button>
                    </>
                  )}

                  {orderError && (
                    <div className="message message-error mt-4">
                      {orderError}
                    </div>
                  )}

                  {orderMessage && (
                    <div className="message message-success mt-4">
                      <p>{orderMessage}</p>

                      {orderStatus && (
                        <p className="mt-2">
                          Status: <strong>{orderStatus}</strong>
                        </p>
                      )}
                    </div>
                  )}
                </section>
              </div>
            )}
          </div>
        </div>
      </section>
    </main>
  );
}
