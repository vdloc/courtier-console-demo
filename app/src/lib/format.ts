/** Metres, to the millimetre where it matters, without trailing noise. */
export function metres(value: number): string {
  return `${value.toFixed(value < 10 ? 2 : 1)} m`;
}

const ELEMENT_LABELS: Record<string, string> = {
  column: 'Steel Column',
  beam_x: 'Steel Beam',
  beam_y: 'Steel Beam',
  brace: 'Steel Brace',
  foundation: 'Pad Foundation',
  base_plate: 'Base Plate',
  end_plate: 'End Plate',
  splice_plate: 'Splice Plate',
  gusset: 'Gusset Bracket',
  stiffener: 'Stiffener Rib',
  bolt: 'Bolt Assembly',
  weld: 'Fillet Weld',
  pipe: 'Service Pipe',
  guard_rail: 'Edge Protection Rail',
  guard_post: 'Edge Protection Post',
  toe_board: 'Toe Board',
};

/** Turn a generator element_type into something a person reads. */
export function elementLabel(elementType: string): string {
  return ELEMENT_LABELS[elementType] ?? elementType.replace(/_/g, ' ');
}

/**
 * Short grid-addressed code for the inspector heading, e.g. "B01".
 * Derived from the grid reference so it stays stable across rebuilds.
 */
export function componentCode(elementType: string, gridRef: string): string {
  const prefix = elementType.startsWith('beam')
    ? 'B'
    : elementType === 'column'
      ? 'C'
      : elementType === 'foundation'
        ? 'F'
        : elementType === 'pipe'
          ? 'P'
          : 'X';
  const digits = gridRef.replace(/[^0-9]/g, '').slice(0, 2).padStart(2, '0');
  return `${prefix}${digits}`;
}

/** Material grade pulled out of the generator's spec string. */
export function materialGrade(spec: string): string {
  const match = spec.match(/\b(S\d{3}[A-Z0-9]*|C\d{2}\/\d{2}|B500B|M\d{2})\b/);
  return match ? match[0] : spec.split(',')[0];
}
