import { useMemo } from 'react';
import { Html, Line } from '@react-three/drei';
import { Vector3 } from 'three';
import { useViewerStore } from '../store/useViewerStore';
import { metres } from '../lib/format';

/**
 * Two-point measurement tool.
 *
 * This component only DRAWS the result. Picking lives on the model itself,
 * in Structure's `onPointerDown`: a catcher surface here would have to sit in
 * front of the frame to receive the clicks, and would then swallow every
 * selection click as well.
 */
export function Measure() {
  const measuring = useViewerStore((s) => s.measuring);
  const points = useViewerStore((s) => s.measurePoints);

  const distance = useMemo(() => {
    if (points.length < 2) return null;
    return new Vector3(...points[0].position).distanceTo(
      new Vector3(...points[1].position),
    );
  }, [points]);

  const midpoint = useMemo(() => {
    if (points.length < 2) return null;
    return new Vector3(...points[0].position)
      .add(new Vector3(...points[1].position))
      .multiplyScalar(0.5);
  }, [points]);

  if (!measuring && points.length === 0) return null;

  return (
    <group>
      {points.map((point, index) => (
        <mesh key={index} position={point.position}>
          <sphereGeometry args={[0.09, 16, 16]} />
          <meshBasicMaterial color="#38bdf8" depthTest={false} />
        </mesh>
      ))}

      {points.length === 2 && (
        <Line
          points={[points[0].position, points[1].position]}
          color="#38bdf8"
          lineWidth={2}
          dashed={false}
          depthTest={false}
        />
      )}

      {distance !== null && midpoint && (
        <Html position={midpoint} center distanceFactor={12}>
          <div className="measure-label">{metres(distance)}</div>
        </Html>
      )}
    </group>
  );
}
