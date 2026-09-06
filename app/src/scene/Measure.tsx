import { useMemo } from 'react';
import { Html, Line } from '@react-three/drei';
import { Vector3 } from 'three';
import type { ThreeEvent } from '@react-three/fiber';
import { useViewerStore } from '../store/useViewerStore';
import { metres } from '../lib/format';

/**
 * Two-point measurement tool.
 *
 * Points are taken from the raycast hit position, not from object origins, so
 * a measurement is between the surfaces the user actually clicked - which is
 * what a site dimension is. Snapping to origins would silently measure
 * centre-to-centre and be wrong by half a section depth at each end.
 */
export function Measure() {
  const measuring = useViewerStore((s) => s.measuring);
  const points = useViewerStore((s) => s.measurePoints);
  const addPoint = useViewerStore((s) => s.addMeasurePoint);

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

  const onPointerDown = (event: ThreeEvent<PointerEvent>) => {
    if (!measuring) return;
    event.stopPropagation();
    addPoint({
      position: [event.point.x, event.point.y, event.point.z],
      objectName: event.object.name,
    });
  };

  return (
    <group>
      {/* An invisible catcher plane would block selection, so the capture
          surface is the model itself: this group only draws the result. */}
      <mesh
        visible={false}
        onPointerDown={onPointerDown}
        position={[0, 0, 0]}
      >
        <boxGeometry args={[0.001, 0.001, 0.001]} />
      </mesh>

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
