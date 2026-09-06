import type { Object3D } from 'three';

/**
 * Discipline prefixes written by the Blender generator. They double as the
 * viewer's grouping, which is why the exporter's naming schema is worth
 * keeping strict: the UI derives what it can from the file rather than from a
 * table that has to be kept in step by hand.
 */
export type Discipline = 'STR' | 'ARC' | 'MEP' | 'TMP';

/** Layer groups, exactly as they appear as parent nodes in the GLB. */
export const LAYERS = [
  'Foundation',
  'Columns',
  'Beams',
  'Pipes',
  'Connections',
  'Accessories',
] as const;

export type LayerName = (typeof LAYERS)[number];

/**
 * Component metadata read from glTF `extras`, i.e. the Blender custom
 * properties written by generate_structure.py `tag()`.
 */
export interface ComponentData {
  discipline: Discipline;
  element_type: string;
  level: string;
  grid_ref: string;
  section: string;
  material_spec: string;
}

/** What the inspector shows for the selected object. */
export interface ComponentInfo extends ComponentData {
  name: string;
  /** Longest bounding-box dimension in metres - the member's length. */
  length: number;
  /** Not in the model: derived from where the construction timeline sits. */
  status: 'Installed' | 'In progress' | 'Not started';
  object: Object3D;
}

export interface TimelinePhase {
  name: string;
  start: number;
  end: number;
  startFrame: number;
  endFrame: number;
}

export interface TimelineManifest {
  fps: number;
  duration: number;
  frameStart: number;
  frameEnd: number;
  clipName: string;
  phases: TimelinePhase[];
}

export type CameraShot = 'hero' | 'corner' | 'detail' | 'elevation';

export interface MeasurementPoint {
  position: [number, number, number];
  objectName: string;
}
