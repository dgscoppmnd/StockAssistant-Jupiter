export type AnalyzeResponse = {
  response?: string;
  [key: string]: unknown;
};

export type AgentChatRequest = {
  prompt: string;
  provider?: "openai" | "ollama";
  use_web?: boolean;
  use_tools?: boolean;
  max_web_results?: number;
  max_tool_results?: number;
};

export type WebSearchResult = {
  title: string;
  url: string;
  snippet: string;
  source: string;
};

export type AgentChatResponse = {
  agent: string;
  provider?: string;
  model?: string;
  used_fallback?: boolean;
  response?: string;
  responses?: {
    primary?: {
      response?: string;
      provider?: string;
      model?: string;
      used_fallback?: boolean;
    };
    secondary?: {
      response?: string;
      provider?: string;
      model?: string;
      used_fallback?: boolean;
    } | null;
  };
  web_results?: WebSearchResult[];
  tool_results?: Record<string, unknown>;
  meta?: {
    selected_provider?: "openai" | "ollama";
    ai?: {
      mode?: string;
      preferred_provider?: string;
      fallback_provider?: string;
      providers?: Record<string, {
        provider?: string;
        configured?: boolean;
        available?: boolean;
        model?: string;
        cooldown_active?: boolean;
        cooldown_until?: string | null;
      }>;
    };
    [key: string]: unknown;
  };
};








export type User = {
  id: number;
  nombre: string;
  apellido: string;
  email: string;
  descripcion: string;
  password: string;
  status: number;
  startline: string | null;
  deadline: string | null;
  created_at: string;
  updated_at: string;
  auth_provider?: string | null;
  google_sub?: string | null;
  avatar_url?: string | null;
  given_name?: string | null;
  family_name?: string | null;
  email_verified?: boolean | null;
  last_login_at?: string | null;
};

export type AuthUser = Omit<User, "password">;

export type GoogleLoginPayload = {
  credential: string;
};

export type PasswordLoginPayload = {
  email: string;
  password: string;
};

export type AuthSessionResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: AuthUser;
};

export type UserCreatePayload = {
  nombre: string;
  apellido: string;
  email: string;
  descripcion: string;
  password: string;
  status: number;
  startline?: string | null;
  deadline?: string | null;
};

export type UserUpdatePayload = {
  nombre: string;
  apellido: string;
  email: string;
  descripcion: string;
  password: string;
  status: number;
  startline?: string | null;
  deadline?: string | null;
};

export type Product = {
  pk_product: number;
  cdgo_producto_externo: string | null;
  name_product: string;
  description_product: string | null;
  disabled: boolean;
  price: number | null;
  unit: number;
  final_price: number | null;
  discount: number | null;
  discount_end_date: string | null;
  fk_currency: number;
  currency: string | null;
  user_rating: number;
  link: string | null;
  creation_date: string | null;
  fk_last_update_user: number;
  last_update: string | null;
  supplier: string | null;
  default_image_url?: string | null;
};

export type ProductImage = {
  id: number;
  product_id?: number | null;
  url: string;
  mime_type: string;
  file_size: number;
  original_filename?: string | null;
  is_default: boolean;
  created_at: string;
};

export type ProductImageUploadResponse = ProductImage;

export type ProductCreatePayload = {
  cdgo_producto_externo?: string | null;
  name_product: string;
  description_product?: string | null;
  disabled?: boolean;
  price?: number | null;
  unit?: number;
  final_price?: number | null;
  discount?: number | null;
  discount_end_date?: string | null;
  fk_currency?: number;
  currency?: string | null;
  user_rating?: number;
  link?: string | null;
  creation_date?: string | null;
  fk_last_update_user?: number;
  last_update?: string | null;
  supplier?: string | null;
};

export type ProductUpdatePayload = ProductCreatePayload;

export type InventoryWarehouse = {
  id: number;
  code: string;
  name: string;
  description?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type InventoryStockItem = {
  product_id: number;
  product_name: string;
  warehouse_id: number;
  warehouse_code: string;
  warehouse_name: string;
  physical_qty: number;
  reserved_qty: number;
  available_qty: number;
  base_unit_code: string;
  reorder_point: number;
  reorder_quantity: number;
  currency?: string | null;
};

export type InventoryMovement = {
  id: number;
  movement_type: string;
  product_id: number;
  warehouse_id?: number | null;
  warehouse_destination_id?: number | null;
  quantity: number;
  quantity_signed: number;
  base_unit_code: string;
  document_type?: string | null;
  document_id?: number | null;
  operation_key: string;
  reason?: string | null;
  user_name: string;
  created_at: string;
};

export type InventoryDashboard = {
  total_products: number;
  total_warehouses: number;
  total_stock_units: number;
  total_reserved_units: number;
  total_available_units: number;
  low_stock_items: number;
  warehouses: InventoryWarehouse[];
  recent_movements: InventoryMovement[];
  stock_snapshot: InventoryStockItem[];
};

export type ExecutiveDashboard = {
  period_days: number;
  generated_at: string;
  metrics: {
    service_level_pct: number | null;
    turnover: number | null;
    excess_units: number;
    excess_items: number;
    potential_savings: number | null;
    potential_savings_note: string;
  };
  priority_purchases: Array<Record<string, string | number | null>>;
  alerts: Array<Record<string, string | number | null>>;
  stock_evolution: Array<{ day: string; entries: number; consumption: number }>;
  forecast_vs_available: Array<{ product_id: number; product_name: string; available_qty: number; dispatched_qty: number }>;
  risk_distribution: Array<{ label: string; value: number }>;
  supplier_comparison: Array<{ supplier_code: string | null; name: string; average_cost: number | null; compliance_pct: number | null; lead_time_days: number | null; orders: number }>;
};

export type InventoryWarehousePayload = {
  code: string;
  name: string;
  description?: string;
  is_active?: boolean;
};

export type InventoryProductConfigPayload = {
  product_id: number;
  base_unit_code: string;
  reorder_point: number;
  reorder_quantity: number;
  allow_negative_stock?: boolean;
};

export type InventoryLinePayload = {
  product_id: number;
  quantity: number;
  unit_code: string;
  unit_price?: number;
  currency_code?: string | null;
  exchange_rate?: number;
  exchange_rate_date?: string | null;
};

export type InventoryOperationResponse = {
  status: string;
  document_type: string;
  document_id: number;
  document_number: string;
  operation_key: string;
  movement_ids: number[];
};

export type ExternalSourceStatus = {
  name: string;
  available: boolean;
  mode: string;
  detail: string;
};

export type StockAlert = {
  product_id: number;
  product_name: string;
  warehouse_id: number;
  warehouse_name: string;
  available_qty: number;
  reorder_point: number;
  reorder_quantity: number;
  base_unit_code: string;
};

export type PurchaseRecommendation = {
  product_id: number;
  product_name: string;
  recommended_qty: number;
  base_unit_code: string;
  estimated_unit_cost?: number | null;
  estimated_landed_cost?: number | null;
  currency: string;
  explanation: string;
  offers: Array<{ merchant?: string; price: number; currency: string; url?: string; country: string }>;
};

export type SalesForecast = { product_id: number; product_name: string; forecast_qty: number; daily_average: number; horizon_days: number; trend: string };
export type FinancialSummary = { revenue: number; cost: number; margin: number; margin_percent: number; currency_basis: string };
export type CustomerSupportAnswer = { answer: string; sources: Array<{ title: string; source: string; expires_at?: string | null }>; stock: Array<{ warehouse: string; available_qty: number; unit: string }> };

export type AutomationRule = { id: number; code: string; name: string; description: string; is_active: boolean; interval_minutes: number; last_run_at?: string | null };
export type AutomationRun = { id: number; rule_code: string; initiated_by: string; status: string; started_at: string; completed_at?: string | null };
export type PurchaseProposal = { id: number; product_name: string; warehouse_name: string; suggested_qty: number; base_unit_code: string; status: string; justification: string; created_at: string };
export type ExecutiveResult = { decision_id: number; routed_agent: string; tool: string; execution_policy: string; result: Record<string, unknown> };

export type MasterRecord = { id: number; created_at?: string; updated_at?: string; [key: string]: unknown };
export type MasterField = { key: string; label: string; type?: "text" | "number" | "decimal" | "textarea" | "checkbox"; required?: boolean; placeholder?: string };
