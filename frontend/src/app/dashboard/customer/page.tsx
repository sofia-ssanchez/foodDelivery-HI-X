"use client";

import { useEffect, useMemo, useState } from "react";

type Restaurant = {
  id: number;
  name: string;
};

type MenuItem = {
  id: number;
  name: string;
  description?: string;
  price: number;
};

type CartItem = MenuItem & {
  quantity: number;
};

type OrderResponse = {
  id?: number;
  status?: string;
  message?: string;
};

// We will confirm these with Kailee once her backend is pushed.
const API_BASE = "http://localhost:8000";

const RESTAURANTS_ENDPOINT = `${API_BASE}/api/restaurants/`;

const menuEndpoint = (restaurantId: number) =>
  `${API_BASE}/api/restaurants/${restaurantId}/menu/`;

const ORDERS_ENDPOINT = `${API_BASE}/api/orders/`;

export default function CustomerDashboard() {
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

  // Load restaurants when the customer dashboard opens.
  useEffect(() => {
    const loadRestaurants = async () => {
      setLoadingRestaurants(true);
      setRestaurantError("");

      try {
        const response = await fetch(RESTAURANTS_ENDPOINT, {
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

  // Load the menu for the restaurant the customer selects.
  const selectRestaurant = async (restaurant: Restaurant) => {
    setSelectedRestaurant(restaurant);

    setMenuItems([]);
    setCart([]);

    setMenuError("");
    setOrderError("");
    setOrderMessage("");
    setOrderStatus("");

    setLoadingMenu(true);

    try {
      const response = await fetch(menuEndpoint(restaurant.id), {
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

    if (cart.length === 0) {
      setOrderError("Your order is empty.");
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

      const response = await fetch(ORDERS_ENDPOINT, {
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

  return (
    <main className="page-container botanical-background">
      <section className="page-content">

        {/* Header */}
        <header className="mb-8">
          <p className="eyebrow">
            Five Leaf Clover
          </p>

          <h1 className="page-title mt-3">
            Customer Dashboard
          </h1>

          <p className="body-text mt-3">
            Browse restaurants, view menus, and place your order.
          </p>
        </header>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">

          {/* Restaurants */}
          <section className="form-card">
            <h2 className="section-title">
              Restaurants
            </h2>

            <p className="body-text mt-2">
              Choose a restaurant to view its menu.
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

                return (
                  <button
                    key={restaurant.id}
                    type="button"
                    className={
                      isSelected
                        ? "btn btn-primary btn-full"
                        : "btn btn-full"
                    }
                    onClick={() =>
                      selectRestaurant(restaurant)
                    }
                  >
                    {restaurant.name}
                  </button>
                );
              })}
            </div>
          </section>

          {/* Menu */}
          <section className="form-card">
            <h2 className="section-title">
              Menu
            </h2>

            {!selectedRestaurant && (
              <p className="body-text mt-3">
                Select a restaurant to view its menu.
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
                  {menuItems.map((item) => (
                    <article
                      key={item.id}
                      className="rounded-xl border p-4"
                    >
                      <h3 className="font-semibold">
                        {item.name}
                      </h3>

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
                        className="btn btn-primary btn-full mt-4"
                        onClick={() => addToCart(item)}
                      >
                        Add to Order
                      </button>
                    </article>
                  ))}
                </div>
              </>
            )}
          </section>

          {/* Order */}
          <section className="form-card">
            <h2 className="section-title">
              Your Order
            </h2>

            {!selectedRestaurant && (
              <p className="body-text mt-3">
                Choose a restaurant to begin your order.
              </p>
            )}

            {selectedRestaurant &&
              cart.length === 0 && (
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
                      onClick={() =>
                        decreaseQuantity(item.id)
                      }
                    >
                      -
                    </button>

                    <span>
                      {item.quantity}
                    </span>

                    <button
                      type="button"
                      className="btn"
                      onClick={() =>
                        increaseQuantity(item.id)
                      }
                    >
                      +
                    </button>
                  </div>

                  <p className="mt-3 font-semibold">
                    Subtotal: $
                    {(
                      Number(item.price) *
                      item.quantity
                    ).toFixed(2)}
                  </p>

                  <button
                    type="button"
                    className="btn btn-full mt-3"
                    onClick={() =>
                      removeFromCart(item.id)
                    }
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
                  disabled={placingOrder}
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
                    Status:{" "}
                    <strong>{orderStatus}</strong>
                  </p>
                )}
              </div>
            )}
          </section>
        </div>
      </section>
    </main>
  );
}