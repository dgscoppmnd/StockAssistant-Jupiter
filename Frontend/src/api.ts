import type {
  AuthSessionResponse,
  AuthUser,
  AgentChatRequest,
  AgentChatResponse,
  AnalyzeResponse,
  InventoryDashboard,
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
  Product,
  ProductCreatePayload,
  ProductImage,
  ProductImageUploadResponse,
  ProductUpdatePayload,
  Task,
  TaskImageUploadResponse,
  TaskChildrenStatusCount,
  TaskCreatePayload,
  TaskUpdatePayload,
  GoogleLoginPayload,
  PasswordLoginPayload,
  User,
  UserCreatePayload,
  UserUpdatePayload,
  WorksheetRegister,
  WorksheetRegisterPayload,
} from "./types";

const API_BASE = "/api";
const API_KEY_STORAGE_KEY = "kitia-api-key";
const SESSION_STORAGE_KEY = "kitia-session-token";
const ENV_API_KEY =
  (import.meta.env as Record<string, string | undefined>).VITE_KITIA_API_KEY?.trim() ||
  (import.meta.env as Record<string, string | undefined>).KITIA_API_KEYS?.trim() ||
  "";

type BackendTask = Omit<Task, "fecha_completada"> & { datetaskcompleted?: string | null };

function fromBackendTask(task: BackendTask): Task {
  const { datetaskcompleted, ...rest } = task;
  return {
    ...rest,
    fecha_completada: datetaskcompleted ?? null
  };
}

function toBackendTaskPayload<T extends { fecha_completada?: string | null }>(payload: T): Omit<T, "fecha_completada"> & {
  datetaskcompleted?: string | null;
} {
  const { fecha_completada, ...rest } = payload;
  return {
    ...rest,
    datetaskcompleted: fecha_completada ?? null
  };
}

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
  const authHeaders = sessionToken
    ? { Authorization: `Bearer ${sessionToken}` }
    : apiKey
      ? { "X-API-Key": apiKey }
      : {};
  const isFormData = options?.body instanceof FormData;

  const response = await fetch(url, {
    headers: {
      Accept: "application/json",
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...authHeaders,
      ...(options?.headers ?? {})
    },
    ...options
  });

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
    const detail = typeof parsed === "string" ? parsed : JSON.stringify(parsed, null, 2);
    throw new Error(detail || `HTTP ${response.status}`);
  }

  return parsed as T;
}

export async function analyzeWithSystemPrompt(prompt: string): Promise<AnalyzeResponse> {
  const url = `${API_BASE}/analyze-system?prompt=${encodeURIComponent(prompt)}`;
  return request<AnalyzeResponse>(url, { method: "POST", headers: { "Content-Type": "application/json" } });
}

export async function analyzeWithKitiaAgent(payload: AgentChatRequest): Promise<AgentChatResponse> {
  return request<AgentChatResponse>(`${API_BASE}/agents/kitia/chat`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function fetchInventoryDashboard(): Promise<InventoryDashboard> {
  return request<InventoryDashboard>(`${API_BASE}/inventory/dashboard`, { method: "GET" });
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

// Task API endpoints
export async function fetchTasksForGantt(filters?: {
  userIds?: number[];
  dateFrom?: string;
  dateTo?: string;
  dateField?: "inicio" | "fin" | "completada";
}): Promise<Task[]> {
  const params = new URLSearchParams();
  if (filters?.userIds?.length) {
    for (const userId of filters.userIds) {
      params.append("user_ids", String(userId));
    }
  }
  if (filters?.dateFrom) {
    params.append("date_from", filters.dateFrom);
  }
  if (filters?.dateTo) {
    params.append("date_to", filters.dateTo);
  }
  if (filters?.dateField) {
    params.append("date_field", filters.dateField);
  }
  const query = params.toString();
  const url = query ? `${API_BASE}/tasks/gantt?${query}` : `${API_BASE}/tasks/gantt`;
  const tasks = await request<BackendTask[]>(url, { method: "GET" });
  return tasks.map(fromBackendTask);
}

export async function fetchTaskChildrenStatusCount(taskId: number): Promise<TaskChildrenStatusCount> {
  return request<TaskChildrenStatusCount>(`${API_BASE}/tasks/${taskId}/children/status/count`, {
    method: "GET"
  });
}

export async function createTask(payload: TaskCreatePayload): Promise<Task> {
  const created = await request<BackendTask>(`${API_BASE}/tasks/`, {
    method: "POST",
    body: JSON.stringify(toBackendTaskPayload(payload))
  });
  return fromBackendTask(created);
}

export async function updateTask(taskId: number, payload: TaskUpdatePayload): Promise<Task> {
  const updated = await request<BackendTask>(`${API_BASE}/tasks/${taskId}`, {
    method: "PUT",
    body: JSON.stringify(toBackendTaskPayload(payload))
  });
  return fromBackendTask(updated);
}

export async function deleteTask(taskId: number): Promise<void> {
  await request<void>(`${API_BASE}/tasks/${taskId}`, { method: "DELETE" });
}

export async function moveTask(taskId: number, idPadre: number | null): Promise<Task> {
  return request<Task>(`${API_BASE}/tasks/${taskId}/move`, {
    method: "PATCH",
    body: JSON.stringify({ id_padre: idPadre })
  });
}

export async function importTasksCsv(file: File): Promise<{
  imported_tasks: number;
  created_users: number;
  skipped_rows: number;
  unresolved_relations: string[];
}> {
  const formData = new FormData();
  formData.append("file", file);

  return request(`${API_BASE}/tasks/import/csv`, {
    method: "POST",
    body: formData
  });
}

export async function uploadTaskImage(file: File, taskId?: number | null): Promise<TaskImageUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const query = typeof taskId === "number" ? `?task_id=${encodeURIComponent(String(taskId))}` : "";
  return request<TaskImageUploadResponse>(`${API_BASE}/tasks/images/upload${query}`, {
    method: "POST",
    body: formData,
  });
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

// Worksheet register API endpoints
export async function fetchWorksheetRegisters(filters: {
  year: number;
  month: number;
  user_id?: number;
}): Promise<WorksheetRegister[]> {
  const params = new URLSearchParams({
    year: String(filters.year),
    month: String(filters.month),
  });
  if (filters.user_id !== undefined) {
    params.append("user_id", String(filters.user_id));
  }

  return request<WorksheetRegister[]>(`${API_BASE}/worksheetregister/?${params.toString()}`, {
    method: "GET",
  });
}

export async function createWorksheetRegister(payload: WorksheetRegisterPayload): Promise<WorksheetRegister> {
  return request<WorksheetRegister>(`${API_BASE}/worksheetregister/`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateWorksheetRegister(
  registerId: number,
  payload: WorksheetRegisterPayload
): Promise<WorksheetRegister> {
  return request<WorksheetRegister>(`${API_BASE}/worksheetregister/${registerId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function deleteWorksheetRegister(registerId: number): Promise<void> {
  await request<void>(`${API_BASE}/worksheetregister/${registerId}`, { method: "DELETE" });
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
