import { useViewerStore } from '../store/useViewerStore';
import { componentCode, elementLabel, materialGrade, metres } from '../lib/format';

/**
 * Component inspector.
 *
 * Every value here comes from the GLB's own `extras`, written by the Blender
 * generator - nothing is looked up in a parallel table that could go stale.
 * Length is measured off the geometry at click time, which is why it stays
 * correct if the grid in CONFIG changes and the model is rebuilt.
 */
export function Inspector() {
  const selected = useViewerStore((s) => s.selected);
  const select = useViewerStore((s) => s.select);

  if (!selected) {
    return (
      <section className="panel-section">
        <div className="panel-header">
          <span className="panel-title">Component</span>
        </div>
        <div className="empty">
          Click any member to inspect it.
          <div className="hint">
            Selection reads the component data embedded in the model.
          </div>
        </div>
      </section>
    );
  }

  const code = componentCode(selected.element_type, selected.grid_ref);

  return (
    <section className="panel-section">
      <div className="panel-header">
        <span className="panel-title">Component</span>
        <button onClick={() => select(null)}>Clear</button>
      </div>
      <div className="panel-body">
        <Field label="Component">
          {elementLabel(selected.element_type)} {code}
        </Field>
        <Field label="Material" mono>
          {materialGrade(selected.material_spec)}
        </Field>
        <Field label="Section" mono>
          {selected.section || '—'}
        </Field>
        <Field label="Length" mono>
          {metres(selected.length)}
        </Field>
        <Field label="Grid reference" mono>
          {selected.grid_ref || '—'}
        </Field>
        <Field label="Level" mono>
          {selected.level}
        </Field>
        <Field label="Status">
          <span className="status" data-state={selected.status}>
            {selected.status}
          </span>
        </Field>
        <Field label="Specification">{selected.material_spec}</Field>
        <Field label="Object ID" mono>
          {selected.name}
        </Field>
      </div>
    </section>
  );
}

function Field({
  label,
  children,
  mono,
}: {
  label: string;
  children: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="field">
      <div className="field-label">{label}</div>
      <div className={mono ? 'field-value mono' : 'field-value'}>{children}</div>
    </div>
  );
}
