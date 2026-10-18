# UI & UX Document
## E-Commerce Application & Product Knowledge Assistant

---

### 1. Existing Core E-Commerce Screens (Preserved Base)

The existing e-commerce design and screen layouts remain unchanged:

#### Customer Screens
1. **Home (`/`):** Welcome banner, search bar, category filters, and product grid.
2. **Product Listing:** Filtered/searched grid of products with image placeholder, name, price, and category badge.
3. **Product Details (`/product/:id`):** Large image display, title, category, price, stock availability badge, full product description, quantity selector, and "Add to Cart" button.
4. **Cart (`/cart`):** List of added items, item count adjustments, subtotal, and "Proceed to Checkout" button.
5. **Checkout (`/checkout`):** Order summary, shipping delivery address form, and simulated "Place Order" button.
6. **Order Confirmation (`/order-confirmation`):** Success banner, order ID, and return-to-shop link.
7. **Order History (`/order-history`):** List of past customer orders with dates, total amounts, and fulfillment statuses.
8. **Login (`/login`):** Email and password input fields with "Login" submission.
9. **Register (`/register`):** Name, email, and password registration form.
10. **Profile (`/profile`):** Current user name, email, link to order history, and logout action.

#### Admin Screens
1. **Admin Login (`/admin`):** Dedicated administrator authentication.
2. **Admin Dashboard:** Navigation cards to products, categories, and orders.
3. **Product Management (`/admin/products`):** Catalog table with "Add New Product" modal and edit/delete actions.
4. **Category Management (`/admin/categories`):** Category list with creation and delete controls.
5. **Order Management (`/admin/orders`):** Order table with status update dropdowns (`Pending`, `Processing`, `Shipped`, `Delivered`).

---

### 2. Product Knowledge Assistant UX (Agentic RAG)

The assistant uses **one single, unified entry point** that works seamlessly across all pages without altering or cluttering the existing e-commerce layout.

#### A. The Single Entry Point: Floating Assistant Drawer
* **Visual Anchor:** A persistent, unobtrusive floating button fixed at the bottom-right of the viewport:
  ```text
  [ 💬 Product Assistant ]
  ```
* **Interaction:** Clicking the button smoothly opens a compact, slide-over drawer (or floating card) on the right side of the screen.
* **Closing:** A simple "✖" button or clicking outside the drawer minimizes it back to the floating icon.

---

### 3. Context-Aware Behavior (Product Page vs. General Store)

The assistant dynamically detects where the customer is browsing:

#### Case 1: Asking from a Product Details Page (`/product/:id`)
* **Trigger:** Customer opens the assistant while viewing a specific product (e.g., *Lumina Wireless Bluetooth Mouse*), or clicks a secondary inline helper button on the product page (*"Have a question about this product?"*).
* **Context Chip:** A clear tag appears at the top of the assistant drawer:
  ```text
  [ 🏷️ Active Context: Lumina Wireless Bluetooth Mouse  (✖ Clear) ]
  ```
* **Question Box Placeholder:** 
  `"Ask about setup, specs, or troubleshooting for this mouse..."`
* **Backend Behavior:** The `product_id` is automatically attached to the request, so the agent prioritizes the manual for this specific product.

#### Case 2: Asking from Any Other Page (Home, Cart, Profile)
* **Trigger:** Customer clicks the floating assistant button while browsing the catalog or checking out.
* **Context Chip:** Displays a general store scope:
  ```text
  [ 📚 Scope: All Store Product Manuals ]
  ```
* **Question Box Placeholder:** 
  `"Ask about any product manual (e.g. 'How do I pair the Lumina Mouse?')..."`
* **Backend Behavior:** The agent identifies which product the user is referring to from the question itself.

---

### 4. Assistant Component Anatomy & State Definitions

The assistant drawer contains four primary zones:
1. **Header Zone:** Title ("Product Knowledge Assistant"), Active Context Chip, and Close Button.
2. **Messages Zone:** Scrollable conversation history containing user questions and assistant responses.
3. **Status / Loading Zone:** Visual feedback while the agent is searching and evaluating documents.
4. **Input Zone:** Question input field and send action button.

```text
┌──────────────────────────────────────────────────┐
│ 💬 Product Knowledge Assistant               [✖] │
│ [🏷️ Lumina Wireless Mouse                 (✖)] │
├──────────────────────────────────────────────────┤
│                                                  │
│  [User]                                          │
│  How do I pair this mouse to my laptop?          │
│                                                  │
│  [Assistant]                                     │
│  To pair the mouse:                              │
│  1. Turn on the power switch on the bottom.      │
│  2. Hold the Connect button for 3 seconds.       │
│  3. When the blue LED flashes, select it on PC.  │
│                                                  │
│  📄 Source: wireless_mouse_manual.md (Sec. 2)    │
│                                                  │
├──────────────────────────────────────────────────┤
│ 🔍 Searching approved product manuals...         │
├──────────────────────────────────────────────────┤
│ [ Ask about setup, specs, or troubleshooting... ]│
│                                      [ Send ➔ ] │
└──────────────────────────────────────────────────┘
```

---

### 5. Detailed Visual States & Message Types

#### 1. Question Box
* **Element:** An accessible text input field.
* **Styling:** Styled to match the dark/neutral theme (`var(--bg-secondary)` background, clean border).
* **Behavior:** Auto-focuses on open. Supports multi-line questions or single line. Disabled during active requests.

#### 2. Ask Action
* **Element:** A prominent "Send" button (`btn-primary`) with an arrow/send icon.
* **Triggers:**
  - Clicking the "Send" button.
  - Pressing the `Enter` key (without `Shift`).
* **Validation:** Disabled if the question box is empty or contains only whitespace.

#### 3. Loading State (Multi-Step Agentic Feedback)
* **Visual:** A subtle pulsing indicator and status message above the input box:
  ```text
  ⚡ Searching approved product manuals...
  ```
* **UX Purpose:** Assures the customer that the system is actively retrieving documentation, preventing duplicate submissions.

#### 4. Answer Area (Grounded Response)
* **Visual:** Clean, distinct message bubble for the assistant (`var(--bg-card)` with high-contrast text).
* **Formatting:** Renders clean bullet points, numbered lists, or short paragraphs for readability.

#### 5. Source / Manual Reference Area
* **Visual:** A small, subdued badge directly beneath the assistant's answer:
  ```text
  📄 Source: Lumina Wireless Mouse User Guide (Section 2: Bluetooth Setup)
  ```
* **UX Purpose:** Establishes credibility, provides transparency, and lets the user know the answer came from an official manual.

#### 6. No-Information Message (Grounded Fallback)
* **When it occurs:** The customer asks a question about a feature or detail not covered in any approved manual.
* **Visual:** A polite notification bubble with an informational icon:
  ```text
  ℹ️ I'm sorry, but that information is not available in the approved product manuals for this item.
  ```
* **UX Rule:** Never speculate, guess, or provide unverified advice.

#### 7. Clarification Message (Ambiguity Handler)
* **When it occurs:** The customer asks an ambiguous question without specifying the product (e.g., asking *"How do I charge it?"* from the Home page).
* **Visual:** A helpful prompt offering guidance:
  ```text
  ❓ Could you please specify which product you are asking about? 
  For example: "How do I charge the Lumina Wireless Mouse?"
  ```

#### 8. Error Message (System & Auth Safeguard)
* **When it occurs:** Network disconnection, server timeout, or unauthenticated request (401).
* **Visual:** A clean, red-tinted alert box with actionable advice:
  - *If not logged in:*
    ```text
    🔒 Please log in to your account to use the Product Knowledge Assistant. [Login Here]
    ```
  - *If network/server error:*
    ```text
    ⚠️ Unable to reach the knowledge assistant. Please check your connection and try again.
    ```

---

### 6. Verification Against BRD.md

| BRD Requirement | UI/UX Design Fulfillment | Status |
| :--- | :--- | :--- |
| **Keep existing app base** | Core 10 customer screens & 5 admin screens remain untouched. | **Compliant** |
| **Single assistant entry point** | One floating assistant drawer across all screens. | **Compliant** |
| **Use existing product context** | Automatically captures `product_id` and name when opened from `/product/:id`. | **Compliant** |
| **Strict grounding & citations** | Dedicated Source Reference area displays manual name and section. | **Compliant** |
| **Zero hallucination / absence** | Distinct "No-Information Message" for questions not covered in manuals. | **Compliant** |
| **Authentication preservation** | Error state prompts customer to log in if JWT token is absent. | **Compliant** |
