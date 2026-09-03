import { useEffect, useState } from "react";
import type { AuthUser } from "../../types";

type HeaderMainProps = {
	title: string;
	user: AuthUser | null;
	sessionRemainingSeconds: number;
	onLogout: () => void;
};

function formatRemainingTime(seconds: number): string {
	const safe = Math.max(seconds, 0);
	const hours = Math.floor(safe / 3600);
	const minutes = Math.floor((safe % 3600) / 60);
	const secs = safe % 60;
	return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

export default function HeaderMain({
	title,
	user,
	sessionRemainingSeconds,
	onLogout,
}: HeaderMainProps) {
	const [collapsed, setCollapsed] = useState<boolean>(() => window.localStorage.getItem("kitia-header-collapsed") === "1");

	useEffect(() => {
		window.localStorage.setItem("kitia-header-collapsed", collapsed ? "1" : "0");
	}, [collapsed]);

	return (
		<header className={`content-header portal-header${collapsed ? " is-collapsed" : ""}`}>
			{!collapsed ? (
				<>
					<div className="portal-header-leading">
						<p className="headline-kicker">Plataforma operativa</p>
						<h2>{title}</h2>
					</div>
					<div className="portal-user-block">
						<div className="portal-user-card">
							<div className="portal-user-ident">
								{user?.avatar_url ? (
									<img alt="Avatar" className="portal-user-avatar" src={user.avatar_url} />
								) : (
									<span className="portal-user-avatar portal-user-avatar-fallback" aria-hidden="true">
										{user?.nombre?.slice(0, 1) || "U"}
									</span>
								)}
								<div>
									<p className="portal-user-name">{user ? `${user.nombre} ${user.apellido}`.trim() : "Sesion activa"}</p>
									<p className="portal-user-email">{user?.email || ""}</p>
								</div>
							</div>
							<p className="portal-session-expiry">Expira en {formatRemainingTime(sessionRemainingSeconds)}</p>
						</div>
						<button
							aria-expanded={!collapsed}
							aria-label="Minimizar cabecera"
							className="portal-collapse-btn"
							onClick={() => setCollapsed(true)}
							type="button"
						>
							<svg viewBox="0 0 24 24" aria-hidden="true">
								<path d="M6.7 8.3a1 1 0 0 1 1.4 0L12 12.2l3.9-3.9a1 1 0 1 1 1.4 1.4l-4.6 4.6a1 1 0 0 1-1.4 0L6.7 9.7a1 1 0 0 1 0-1.4Z" fill="currentColor" />
							</svg>
						</button>
						<button aria-label="Cerrar sesion" className="chip-btn portal-logout-btn" onClick={onLogout} type="button">
							Salir
						</button>
					</div>
				</>
			) : (
				<>
					<div className="portal-header-compact">
						<h4 className="portal-header-compact-title">{title}</h4>
					</div>
					<div className="portal-header-actions">
						<p className="portal-header-compact-email">
                            {user?.avatar_url ? (
									<img alt="Avatar" className="portal-user-avatar" src={user.avatar_url} />
								) : (
									<span className="portal-user-avatar portal-user-avatar-fallback" aria-hidden="true">
										{user?.nombre?.slice(0, 1) || "U"}
									</span>
								)} {user?.email || ""}
                        </p>
						<button
							aria-expanded={!collapsed}
							aria-label="Expandir cabecera"
							className="portal-collapse-btn"
							onClick={() => setCollapsed(false)}
							type="button"
						>
							<svg viewBox="0 0 24 24" aria-hidden="true">
								<path d="M17.3 15.7a1 1 0 0 1-1.4 0L12 11.8l-3.9 3.9a1 1 0 1 1-1.4-1.4l4.6-4.6a1 1 0 0 1 1.4 0l4.6 4.6a1 1 0 0 1 0 1.4Z" fill="currentColor" />
							</svg>
						</button>
						<button aria-label="Cerrar sesion" className="chip-btn portal-logout-btn icon-only" onClick={onLogout} type="button">
							<svg viewBox="0 0 24 24" aria-hidden="true">
								<path d="M10 3a1 1 0 0 1 0 2H6v14h4a1 1 0 1 1 0 2H5a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5Zm6.3 4.3a1 1 0 0 1 1.4 0l3.9 3.9a1 1 0 0 1 0 1.4l-3.9 3.9a1 1 0 1 1-1.4-1.4L18.6 13H9a1 1 0 1 1 0-2h9.6l-2.3-2.3a1 1 0 0 1 0-1.4Z" fill="currentColor" />
							</svg>
						</button>
					</div>
				</>
			)}
		</header>
	);
}
