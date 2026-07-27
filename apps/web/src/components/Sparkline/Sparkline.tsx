import styles from "./Sparkline.module.css";

export interface SparklineProps {
  data: number[];
  width?: number;
  height?: number;
}

export function Sparkline({ data, width = 120, height = 32 }: SparklineProps) {
  if (data.length === 0) {
    return (
      <div className={styles.empty} style={{ width }}>
        no data
      </div>
    );
  }

  if (data.length === 1) {
    return (
      <svg className={styles.sparkline} width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Single data point">
        <circle cx={width / 2} cy={height / 2} r={2.5} fill="var(--accent)" />
      </svg>
    );
  }

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const stepX = width / (data.length - 1);
  const points = data
    .map((value, index) => {
      const x = index * stepX;
      const y = height - ((value - min) / range) * height;
      return `${x},${y}`;
    })
    .join(" ");

  const trend = data[data.length - 1] - data[0];
  const label = trend > 0 ? "Rising trend" : trend < 0 ? "Falling trend" : "Flat trend";

  return (
    <svg className={styles.sparkline} width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label}>
      <polyline points={points} fill="none" stroke="var(--accent)" strokeWidth={1.5} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}
