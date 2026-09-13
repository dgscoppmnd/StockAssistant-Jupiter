// Manual fixture: visit /tests/combobox-smoke.html on Vite. No API or database writes.
import { useState } from "react";
import { createRoot } from "react-dom/client";
import ProductCombobox from "../src/pages/components/ProductCombobox";
import SupplierCombobox from "../src/pages/components/SupplierCombobox";
import type { Product } from "../src/types";
import "../src/styles.css";

const products: Product[] = Array.from({ length: 30 }, (_, i) => ({
  pk_product: i + 1, cdgo_producto_externo: `TEST-${i + 1}`, name_product: `Café ${i + 1}`,
  description_product: null, disabled: false, price: null, unit: 1, final_price: null,
  discount: null, discount_end_date: null, fk_currency: 1, currency: null, user_rating: 0,
  link: null, creation_date: null, fk_last_update_user: 1, last_update: null, supplier: null,
}));

function Fixture() {
  const [product, setProduct] = useState(0);
  const [supplier, setSupplier] = useState<number | null>(null);
  const [created, setCreated] = useState("");
  return <main style={{ padding: 24 }}>
    <h1>Prueba aislada de selectores</h1>
    <p>Buscar «cafe», seleccionar con teclado o ratón y cerrar con Escape. La lista debe superar el contenedor recortado.</p>
    <div style={{ overflow: "hidden", height: 85, border: "1px solid", maxWidth: 400 }}>
      <ProductCombobox products={products} selectedId={product} disabled={false} loading={false} onSelect={p => setProduct(p.pk_product)} />
    </div>
    <p role="status">Producto seleccionado: {product}</p>
    <div style={{ position: "fixed", bottom: 50, width: "min(400px, calc(100vw - 48px))", overflow: "hidden", height: 85 }}>
      <SupplierCombobox suppliers={[{ id: 1, supplier_code: "P-1", name: "Proveedor de prueba" }]} selectedId={supplier}
        creating={false} disabled={false} loading={false} onSelect={s => setSupplier(Number(s.id))} onCreate={setCreated} />
    </div>
    <p role="status">Proveedor seleccionado: {supplier ?? "ninguno"}. Nuevo: {created || "ninguno"}</p>
  </main>;
}
createRoot(document.getElementById("root")!).render(<Fixture />);
