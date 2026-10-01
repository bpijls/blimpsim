import { useEffect, useMemo, useState } from "react";
import { datasetImageUrl, getAnnotations } from "./api.js";

// Green when fully visible, shading to red as the person is occluded.
const boxColor = (visibility) => `hsl(${Math.round(visibility * 120)} 80% 55%)`;

// Shows recorded frames with their ground-truth boxes drawn on top: the way to
// check that labels line up with what the camera rendered.
export default function DatasetViewer({ name, onClose, onError }) {
  const [coco, setCoco] = useState(null);
  const [index, setIndex] = useState(0);

  useEffect(() => {
    setCoco(null);
    setIndex(0);
    getAnnotations(name).then(setCoco).catch((e) => onError(e.message));
  }, [name, onError]);

  const boxesByImage = useMemo(() => {
    const map = new Map();
    for (const a of coco?.annotations ?? []) {
      if (!map.has(a.image_id)) map.set(a.image_id, []);
      map.get(a.image_id).push(a);
    }
    return map;
  }, [coco]);

  const image = coco?.images[index];
  const boxes = image ? (boxesByImage.get(image.id) ?? []) : [];

  return (
    <div className="viewer">
      <div className="viewer-bar">
        <strong>{name}</strong>
        {image && (
          <>
            <button onClick={() => setIndex(index - 1)} disabled={index === 0}>
              Previous
            </button>
            <input
              type="range"
              min={0}
              max={coco.images.length - 1}
              value={index}
              onChange={(e) => setIndex(Number(e.target.value))}
              aria-label="Frame"
            />
            <button
              onClick={() => setIndex(index + 1)}
              disabled={index === coco.images.length - 1}
            >
              Next
            </button>
            <span className="muted">
              frame {index + 1} of {coco.images.length} · t = {image.t.toFixed(1)} s ·{" "}
              {boxes.length} people
            </span>
          </>
        )}
        <button className="quiet" onClick={onClose}>
          Close
        </button>
      </div>

      {!coco && <p className="muted">Loading…</p>}
      {coco && !image && <p className="muted">This dataset has no frames.</p>}
      {image && (
        <div className="viewer-frame">
          <img src={datasetImageUrl(name, image.file_name)} alt={`Frame ${index + 1}`} />
          <svg viewBox={`0 0 ${image.width} ${image.height}`}>
            {boxes.map((a) => (
              <g key={a.id} stroke={boxColor(a.visibility)} fill={boxColor(a.visibility)}>
                <rect
                  x={a.bbox[0]}
                  y={a.bbox[1]}
                  width={a.bbox[2]}
                  height={a.bbox[3]}
                  fill="none"
                  strokeWidth="1.5"
                />
                <text x={a.bbox[0]} y={a.bbox[1] - 3} stroke="none" fontSize="10">
                  #{a.track_id} {Math.round(a.visibility * 100)}%
                </text>
              </g>
            ))}
          </svg>
        </div>
      )}
    </div>
  );
}
