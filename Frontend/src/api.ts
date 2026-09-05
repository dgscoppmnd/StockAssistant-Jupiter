import type {
  AuthSessionResponse,
  AuthUser,
  AgentChatRequest,
  AgentChatResponse,
  AnalyzeResponse,
  InventoryDashboard,
  ExecutiveDashboard,
  InventoryLinePayload,
  InventoryOperationResponse,
  InventoryProductConfigPayload,
  InventoryWarehouse,
  InventoryWarehousePayload,
  ExternalSourceStatus,
  PurchaseRecommendation,
  StockAlert,
  CustomerSupportAnswer,
  FinancialSummary,
  SalesForecast,
  AutomationRule,
  AutomationRun,
  ExecutiveResult,
  PurchaseProposal,
  MasterRecord,
  Product,
  ProductCreatePayload,
  ProductImage,
  ProductImageUploadResponse,
  ProductUpdatePayload,
  GoogleLoginPayload,
  PasswordLoginPayload,
  User,
  UserCreatePayload,
  UserUpdatePayload,
} from "./types";

const API_BASE = "/api";
const API_KEY_STORAGE_KEY = "stockassistant-api-key";
const SESSION_STORAGE_KEY = "stockassistant-session-token";
const ENV_API_KEY =
  (import.meta.env as Record<string, string | undefined>).VITE_STOCKASSISTANT_API_KEY?.trim() ||
  (import.meta.env as Record<string, string | undefined>).STOCKASSISTANT_API_KEYS?.trim() ||
  "";

export function getApiKey(): string {
  if (typeof window === "undefined") {
    return ENV_API_KEY;
  }
  const localValue = window.localStorage.getItem(API_KEY_STORAGE_KEY)?.trim() ?? "";
  return localValue || ENV_API_KEY;
}

export function setApiKey(value: string): void {
  if (typeof window === "undefined") {
    return;
  }
  const trimmed = value.trim();
  if (!trimmed) {
    window.localStorage.removeItem(API_KEY_STORAGE_KEY);
    return;
  }
  window.localStorage.setItem(API_KEY_STORAGE_KEY, trimmed);
}

export function clearApiKey(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(API_KEY_STORAGE_KEY);
}

export function getSessionToken(): string {
  if (typeof window === "undefined") {
    return "";
  }
  return window.localStorage.getItem(SESSION_STORAGE_KEY)?.trim() ?? "";
}

export function setSessionToken(value: string): void {
  if (typeof window === "undefined") {
    return;
  }
  const trimmed = value.trim();
  if (!trimmed) {
    window.localStorage.removeItem(SESSION_STORAGE_KEY);
    return;
  }
  window.localStorage.setItem(SESSION_STORAGE_KEY, trimmed);
}

export function clearSessionToken(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(SESSION_STORAGE_KEY);
}

export async function validateApiKeyCandidate(candidate: string): Promise<void> {
  const response = await fetch(`${API_BASE}/`, {
    method: "GET",
    headers: {
      Accept: "application/json",
      "X-API-Key": candidate.trim()
    }
  });
  if (!response.ok) {
    const raw = await response.text();
    throw new Error(raw || `HTTP ${response.status}`);
  }
}

function decodeBase64Url(raw: string): string {
  const base64 = raw.replace(/-/g, "+").replace(/_/g, "/");
  const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);
  return atob(padded);
}

export function decodeSessionPayload(token: string): Record<string, unknown> | null {
  const pieces = token.split(".");
  if (pieces.length !== 3) {
    return null;
  }

  try {
    const jsonPayload = decodeBase64Url(pieces[1]);
    return JSON.parse(jsonPayload) as Record<string, unknown>;
  } catch {
    return null;
  }
}

export function getSessionExpiryEpoch(token: string): number | null {
  const payload = decodeSessionPayload(token);
  if (!payload) {
    return null;
  }

  const exp = payload.exp;
  return typeof exp === "number" && Number.isFinite(exp) ? exp : null;
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const sessionToken = getSessionToken();
  const apiKey = sessionToken ? "" : getApiKey();
  const headers = new Headers(options?.headers);
  headers.set("Accept", "application/json");
  if (!(options?.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (sessionToken) headers.set("Authorization", `Bearer ${sessionToken}`);
  else if (apiKey) headers.set("X-API-Key", apiKey);
  const response = await fetch(url, { ...options, headers });

  const raw = await response.text();
  let parsed: unknown = null;

  if (raw) {
    try {
      parsed = JSON.parse(raw);
    } catch {
      parsed = raw;
    }
  }

  if (!response.ok) {
    if (sessionToken && (response.status === 401 || response.status === 403)) {
      clearSessionToken();
    }
    const detail = typeof parsed === "string" ? parsed : parsed === null ? "" : JSON.stringify(parsed, null, 2);
    throw new Error(detail || `HTTP ${response.status}`);
  }

  return parsed as T;
}

export async function analyzeWithSystemPrompt(prompt: string): Promise<AnalyzeResponse> {
  const url = `${API_BASE}/analyze-system?prompt=${encodeURIComponent(prompt)}`;
  return request<AnalyzeResponse>(url, { method: "POST", headers: { "Content-Type": "application/json" } });
}

export async function analyzeWithStockAssistantAgent(payload: AgentChatRequest): Promise<AgentChatResponse> {
  return request<AgentChatResponse>(`${API_BASE}/agents/stockassistant/chat`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function fetchInventoryDashboard(): Promise<InventoryDashboard> {
  return request<InventoryDashboard>(`${API_BASE}/inventory/dashboard`, { method: "GET" });
}

export async function fetchExecutiveDashboard(periodDays: number): Promise<ExecutiveDashboard> {
  return request<ExecutiveDashboard>(`${API_BASE}/inventory/executive-dashboard?period_days=${periodDays}`, { method: "GET" });
}

export async function fetchInventoryWarehouses(): Promise<InventoryWarehouse[]> {
  return request<InventoryWarehouse[]>(`${API_BASE}/inventory/warehouses`, { method: "GET" });
}

export async function createWarehouse(payload: InventoryWarehousePayload): Promise<InventoryWarehouse> {
  return request<InventoryWarehouse>(`${API_BASE}/inventory/warehouses`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function configureInventoryProduct(payload: InventoryProductConfigPayload): Promise<void> {
  await request(`${API_BASE}/inventory/products/config`, {
    method: "PUT",
    body: JSON.stringify(payload)
  });
}

export async function confirmInventoryReceipt(payload: {
  warehouse_id: number;
  supplier_name: string;
  supplier_code?: string;
  purchase_order_number?: string;
  receipt_number?: string;
  operation_key?: string;
  user_name: string;
  notes?: string;
  lines: InventoryLinePayload[];
}): Promise<InventoryOperationResponse> {
  return request<InventoryOperationResponse>(`${API_BASE}/inventory/receipts/confirm`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function transferInventoryStock(payload: {
  source_warehouse_id: number;
  destination_warehouse_id: number;
  user_name: string;
  reason: string;
  operation_key?: string;
  lines: InventoryLinePayload[];
}): Promise<InventoryOperationResponse> {
  return request<InventoryOperationResponse>(`${API_BASE}/inventory/transfers`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function loginWithGoogle(credential: string): Promise<AuthSessionResponse> {
  const payload: GoogleLoginPayload = { credential };
  return request<AuthSessionResponse>(`${API_BASE}/auth/google`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function loginWithPassword(email: string, password: string): Promise<AuthSessionResponse> {
  const payload: PasswordLoginPayload = { email, password };
  return request<AuthSessionResponse>(`${API_BASE}/auth/password`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function fetchCurrentSession(): Promise<AuthUser> {
  return request<AuthUser>(`${API_BASE}/auth/me`, { method: "GET" });
}

export async function logoutSession(): Promise<void> {
  try {
    await request<void>(`${API_BASE}/auth/logout`, { method: "POST" });
  } finally {
    clearSessionToken();
  }
}

// User API endpoints
export async function fetchUsers(): Promise<User[]> {
  return request<User[]>(`${API_BASE}/users/`, { method: "GET" });
}

export async function createUser(payload: UserCreatePayload): Promise<User> {
  return request<User>(`${API_BASE}/users/`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function updateUser(userId: number, payload: UserUpdatePayload): Promise<User> {
  return request<User>(`${API_BASE}/users/${userId}`, {
    method: "PUT",
    body: JSON.stringify(payload)
  });
}

export async function deleteUser(userId: number): Promise<void> {
  await request<void>(`${API_BASE}/users/${userId}`, { method: "DELETE" });
}

// Products API endpoints
export async function fetchProducts(): Promise<Product[]> {
  return request<Product[]>(`${API_BASE}/products/`, { method: "GET" });
}

export async function createProduct(payload: ProductCreatePayload): Promise<Product> {
  return request<Product>(`${API_BASE}/products/`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function updateProduct(productId: number, payload: ProductUpdatePayload): Promise<Product> {
  return request<Product>(`${API_BASE}/products/${productId}`, {
    method: "PUT",
    body: JSON.stringify(payload)
  });
}

export async function deleteProduct(productId: number): Promise<void> {
  await request<void>(`${API_BASE}/products/${productId}`, { method: "DELETE" });
}

export async function fetchProductImages(productId: number): Promise<ProductImage[]> {
  return request<ProductImage[]>(`${API_BASE}/products/${productId}/images`, { method: "GET" });
}

export async function uploadProductImage(
  productId: number,
  file: File,
  makeDefault = false
): Promise<ProductImageUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const query = `?make_default=${encodeURIComponent(makeDefault ? "true" : "false")}`;
  return request<ProductImageUploadResponse>(`${API_BASE}/products/${productId}/images/upload${query}`, {
    method: "POST",
    body: formData,
  });
}

export async function setProductDefaultImage(productId: number, imageId: number): Promise<ProductImage> {
  return request<ProductImage>(`${API_BASE}/products/${productId}/images/${imageId}/default`, {
    method: "PUT",
  });
}

export async function deleteProductImage(productId: number, imageId: number): Promise<void> {
  await request<void>(`${API_BASE}/products/${productId}/images/${imageId}`, {
    method: "DELETE",
  });
}

export async function fetchExternalSourceStatuses(): Promise<ExternalSourceStatus[]> {
  const result = await request<{ sources: ExternalSourceStatus[] }>(`${API_BASE}/agents/sources/status`, { method: "GET" });
  return result.sources;
}

export async function fetchStockAlerts(): Promise<StockAlert[]> {
  const result = await request<{ alerts: StockAlert[] }>(`${API_BASE}/agents/stock/alerts`, { method: "GET" });
  return result.alerts;
}

export async function createPurchaseRecommendation(productId: number): Promise<PurchaseRecommendation> {
  return request<PurchaseRecommendation>(`${API_BASE}/agents/purchasing/recommendations`, {
    method: "POST",
    body: JSON.stringify({ product_id: productId, country: "ES", language: "es" }),
  });
}

export async function processReviewBatch(payload: { product_id: number; source: string; reviews: Array<{ text: string; rating?: number }> }): Promise<{ processed_reviews: number; summary: Record<string, number> }> {
  return request(`${API_BASE}/agents/reviews/batches`, { method: "POST", body: JSON.stringify(payload) });
}

export async function fetchSalesForecast(productId: number): Promise<SalesForecast> {
  return request<SalesForecast>(`${API_BASE}/agents/sales/forecast`, { method: "POST", body: JSON.stringify({ product_id: productId }) });
}

export async function fetchFinancialSummary(productId?: number): Promise<FinancialSummary> {
  const query = productId ? `?product_id=${encodeURIComponent(productId)}` : "";
  return request<FinancialSummary>(`${API_BASE}/agents/financial/summary${query}`, { method: "GET" });
}

export async function fetchCompetition(productId: number): Promise<Record<string, unknown>> {
  return request(`${API_BASE}/agents/competition`, { method: "POST", body: JSON.stringify({ product_id: productId }) });
}

export async function fetchMarketIntelligence(term: string): Promise<Record<string, unknown>> {
  return request(`${API_BASE}/agents/market-intelligence`, { method: "POST", body: JSON.stringify({ term }) });
}

export async function askCustomerSupport(question: string, productId?: number): Promise<CustomerSupportAnswer> {
  return request<CustomerSupportAnswer>(`${API_BASE}/agents/customer-support`, { method: "POST", body: JSON.stringify({ question, product_id: productId || null }) });
}

export async function fetchRisks(): Promise<{ alerts: Array<{ type: string; product_name: string; return_rate: number }> }> {
  return request(`${API_BASE}/agents/risks`, { method: "GET" });
}

export async function askExecutive(payload: { question: string; product_id?: number; agent?: string }): Promise<ExecutiveResult> {
  return request<ExecutiveResult>(`${API_BASE}/executive/query`, { method: "POST", body: JSON.stringify(payload) });
}

export async function fetchAutomationRules(): Promise<AutomationRule[]> {
  return request<AutomationRule[]>(`${API_BASE}/executive/automations`, { method: "GET" });
}

export async function updateAutomationRule(ruleId: number, isActive: boolean): Promise<AutomationRule> {
  return request<AutomationRule>(`${API_BASE}/executive/automations/${ruleId}`, { method: "PUT", body: JSON.stringify({ is_active: isActive }) });
}

export async function runAutomationRule(ruleId: number): Promise<void> {
  await request(`${API_BASE}/executive/automations/${ruleId}/run`, { method: "POST" });
}

export async function fetchAutomationRuns(): Promise<AutomationRun[]> {
  return request<AutomationRun[]>(`${API_BASE}/executive/automations/runs`, { method: "GET" });
}

export async function fetchPurchaseProposals(): Promise<PurchaseProposal[]> {
  return request<PurchaseProposal[]>(`${API_BASE}/executive/purchase-proposals`, { method: "GET" });
}

export async function fetchMasterRecords(resource: string): Promise<MasterRecord[]> {
  return request<MasterRecord[]>(`${API_BASE}/master-data/${encodeURIComponent(resource)}`, { method: "GET" });
}

export async function createMasterRecord(resource: string, values: Record<string, unknown>): Promise<MasterRecord> {
  return request<MasterRecord>(`${API_BASE}/master-data/${encodeURIComponent(resource)}`, { method: "POST", body: JSON.stringify({ values }) });
}

export async function updateMasterRecord(resource: string, recordId: number, values: Record<string, unknown>): Promise<MasterRecord> {
  return request<MasterRecord>(`${API_BASE}/master-data/${encodeURIComponent(resource)}/${recordId}`, { method: "PUT", body: JSON.stringify({ values }) });
}

export async function deleteMasterRecord(resource: string, recordId: number): Promise<void> {
  await request<void>(`${API_BASE}/master-data/${encodeURIComponent(resource)}/${recordId}`, { method: "DELETE" });
}
