import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { useEffect, useMemo, useState, type Dispatch, type SetStateAction } from "react";
import { useAuth } from "./auth";
import StockAssistantPage from "./pages/StockAssistantPage";
import ConfigPage from "./pages/ConfigPage";
import UsersPage from "./pages/UsersPage";
import InventoryPage from "./pages/InventoryPage";
import AgentsOperationsPage from "./pages/AgentsOperationsPage";
import ExecutivePage from "./pages/ExecutivePage";
import ExecutiveDashboardPage from "./pages/ExecutiveDashboardPage";
import MasterDataPage from "./pages/MasterDataPage";
import ProductlistPage from "./pages/productlistPage";
import LoginPage from "./pages/LoginPage";
import HeaderMain from "./pages/components/headerMain";

type ThemeMode = "night" | "day";

type MenuGroup = {
  key: string;
  label: string;
  icon: JSX.Element;
  children: Array<{ to: string; label: string }>;
};

const groups: MenuGroup[] = [
  {
    key: "dashboard",
    label: "Resumen",
    icon: <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20V10h3v10H4Zm6 0V4h4v16h-4Zm7 0v-7h3v7h-3Z" fill="currentColor" /></svg>,
    children: [
      { to: "/dashboard", label: "Resumen ejecutivo" },
      { to: "/agentes", label: "Alertas y análisis" },
      { to: "/ejecutivo", label: "Compras y automatizaciones" },
    ]
  },
  {
    key: "jupiter",
    label: "Proyecto Jupiter",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 3 4 7v5c0 5.2 3.4 8.8 8 10 4.6-1.2 8-4.8 8-10V7l-8-4Zm0 3.3 4.7 2.3v3.2c0 3.5-2 6.1-4.7 7.2-2.7-1.1-4.7-3.7-4.7-7.2V8.6L12 6.3Zm-2 3.2h4c1.1 0 2 .9 2 2v1c0 .7-.3 1.3-.8 1.7l.8 2.3h-2.3l-.6-1.7h-2.2v1.7H8V11.5c0-1.1.9-2 2-2Zm0 2v1.3h4v-1.3h-4Z" fill="currentColor" />
      </svg>
    ),
    children: [
      { to: "/dashboard", label: "Dashboard ejecutivo" },
      { to: "/jupiter", label: "Chat OpenAI + Ollama" },
      { to: "/agentes", label: "Agentes de compras y stock" },
      { to: "/ejecutivo", label: "Centro Ejecutivo y automatizaciones" },
      { to: "/users", label: "Usuarios" }
    ]
  },
  {
    key: "products",
    label: "Productos",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 2 4 6v12l8 4 8-4V6l-8-4Zm0 2.6 4.2 2.1L12 8.8 7.8 6.7 12 4.6Zm-5 4.1 4 2v4.6l-4-2V8.7Zm6 6.6V10.7l4-2v4.6l-4 2Z" fill="currentColor" />
      </svg>
    ),
    children: [
      { to: "/productlist", label: "Lista de productos" },
      { to: "/inventario", label: "Inventario y dashboard" }
    ]
  },  
  {
    key: "config",
    label: "Configuracion",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="m19.4 13 .1-1-.1-1 2.1-1.7-2-3.5-2.6 1a7 7 0 0 0-1.7-1l-.4-2.7h-4l-.4 2.7c-.6.2-1.2.6-1.7 1l-2.6-1-2 3.5L4.6 11c0 .3-.1.7-.1 1s0 .7.1 1L2.5 14.7l2 3.5 2.6-1c.5.4 1.1.8 1.7 1l.4 2.7h4l.4-2.7c.6-.2 1.2-.6 1.7-1l2.6 1 2-3.5L19.4 13ZM12 15.5A3.5 3.5 0 1 1 12 8a3.5 3.5 0 0 1 0 7.5Z" fill="currentColor" />
      </svg>
    ),
    children: [
      { to: "/configuracion", label: "Estado de integraciones" },
      { to: "/maestros/unidades", label: "Unidades de medida" },
      { to: "/maestros/monedas", label: "Monedas" },
      { to: "/maestros/bodegas", label: "Bodegas" },
      { to: "/maestros/proveedores", label: "Proveedores" },
      { to: "/maestros/conversiones", label: "Conversiones de unidad" },
      { to: "/maestros/conocimiento", label: "Base de conocimiento" },
      { to: "/setup", label: "Configuracion de stockassistant" }
    ]
  }
];

function PortalShell({
  theme,
  sidebarCollapsed,
  setSidebarCollapsed,
  openMenu,
  setOpenMenu,
  setTheme,
}: {
  theme: ThemeMode;
  sidebarCollapsed: boolean;
  setSidebarCollapsed: Dispatch<SetStateAction<boolean>>;
  openMenu: string;
  setOpenMenu: Dispatch<SetStateAction<string>>;
  setTheme: Dispatch<SetStateAction<ThemeMode>>;
}) {
  const { user, logout, sessionRemainingSeconds } = useAuth();

  const title = useMemo(() => {
    const active = groups.find((group) => group.key === openMenu);
    return active ? active.label : "Panel";
  }, [openMenu]);

  return (
    <div className={`app-shell theme-${theme}${sidebarCollapsed ? " sidebar-collapsed" : ""}`}>
      <aside className="sidebar">
        <div className="brand-block">
          <div>
            <p className="brand-kicker">stockassistant S.L.</p>
            <h1>Proyecto Jupiter</h1>
          </div>
          <button
            aria-label={sidebarCollapsed ? "Expandir menu" : "Contraer menu"}
            aria-pressed={sidebarCollapsed}
            className="sidebar-toggle"
            onClick={() => setSidebarCollapsed((prev) => !prev)}
            type="button"
          >
            <span className="sidebar-toggle-icon" aria-hidden="true">
              <span />
              <span />
              <span />
            </span>
          </button>
        </div>

        <button
          aria-label="Alternar tema"
          className="theme-switch"
          onClick={() => setTheme((prev) => (prev === "night" ? "day" : "night"))}
          type="button"
        >
          <span className="theme-switch-dot" aria-hidden="true" />
          {theme === "night" ? "Modo nocturno" : "Modo diurno"}
        </button>

        <nav className="menu">
          {groups.map((group) => {
            const expanded = openMenu === group.key;
            return (
              <div className="menu-group" key={group.key}>
                <button
                  className="menu-trigger"
                  type="button"
                  onClick={() => {
                    if (sidebarCollapsed) {
                      setSidebarCollapsed(false);
                      setOpenMenu(group.key);
                      return;
                    }

                    setOpenMenu(expanded ? "" : group.key);
                  }}
                >
                  <span className="menu-trigger-main">
                    <span className="menu-icon" aria-hidden="true">{group.icon}</span>
                    <span className="menu-label">{group.label}</span>
                  </span>
                  <span className="chevron">{expanded ? "-" : "+"}</span>
                </button>
                {expanded && !sidebarCollapsed && (
                  <div className="submenu">
                    {group.children.map((child) => (
                      <NavLink
                        className={({ isActive }) => `submenu-link${isActive ? " active" : ""}`}
                        key={child.to}
                        to={child.to}
                      >
                        {child.label}
                      </NavLink>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </nav>
      </aside>

      <main className="content-area">
        <HeaderMain
          onLogout={() => void logout()}
          sessionRemainingSeconds={sessionRemainingSeconds}
          title={title}
          user={user}
        />

        <section className="page-area">
          <Routes>
            <Route path="/" element={<Navigate replace to="/dashboard" />} />
            <Route path="/dashboard" element={<ExecutiveDashboardPage />} />
            <Route path="/jupiter" element={<StockAssistantPage />} />
            <Route path="/agentes" element={<AgentsOperationsPage />} />
            <Route path="/ejecutivo" element={<ExecutivePage />} />
            <Route path="/users" element={<UsersPage />} />
            <Route path="/productlist" element={<ProductlistPage />} />
            <Route path="/inventario" element={<InventoryPage />} />
            <Route path="/configuracion" element={<ConfigPage />} />
            <Route path="/setup" element={<ConfigPage />} />
            <Route path="/maestros/unidades" element={<MasterDataPage resource="units" />} />
            <Route path="/maestros/monedas" element={<MasterDataPage resource="currencies" />} />
            <Route path="/maestros/bodegas" element={<MasterDataPage resource="warehouses" />} />
            <Route path="/maestros/proveedores" element={<MasterDataPage resource="suppliers" />} />
            <Route path="/maestros/conversiones" element={<MasterDataPage resource="unit-conversions" />} />
            <Route path="/maestros/conocimiento" element={<MasterDataPage resource="knowledge-documents" />} />
            <Route path="*" element={<Navigate replace to="/dashboard" />} />
          </Routes>
        </section>
      </main>
    </div>
  );
}

export default function App() {
  const { user, loading } = useAuth();
  const [openMenu, setOpenMenu] = useState<string>("dashboard");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [theme, setTheme] = useState<ThemeMode>(() => {
    const stored = window.localStorage.getItem("stockassistant-theme");
    return stored === "day" ? "day" : "night";
  });

  useEffect(() => {
    document.body.setAttribute("data-theme", theme);
    window.localStorage.setItem("stockassistant-theme", theme);
  }, [theme]);

  if (loading) {
    return (
      <main className="login-page">
        <section className="login-panel card">
          <div className="login-copy">
            <p className="brand-kicker">stockassistant S.L.</p>
            <h1>Verificando sesión</h1>
            <p className="login-lead">Estamos comprobando tu sesión antes de abrir el portal.</p>
          </div>
        </section>
      </main>
    );
  }

  if (!user) {
    return <LoginPage theme={theme} onToggleTheme={() => setTheme((prev) => (prev === "night" ? "day" : "night"))} />;
  }

  return (
    <PortalShell
      openMenu={openMenu}
      setOpenMenu={setOpenMenu}
      setSidebarCollapsed={setSidebarCollapsed}
      setTheme={setTheme}
      sidebarCollapsed={sidebarCollapsed}
      theme={theme}
    />
  );
}
