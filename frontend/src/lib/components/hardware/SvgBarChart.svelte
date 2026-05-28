<script lang="ts">
  export let values: number[] = [];
  export let labels: string[] = [];
  export let color = '#d8ff00';
  export let unit = '';
  export let title = 'Bar chart';

  const width = 640;
  const height = 180;
  const pad = 18;

  $: maxValue = Math.max(1, ...values);
  $: barWidth = values.length ? (width - pad * 2) / values.length : 0;
</script>

<div>
  <svg class="h-48 w-full" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" role="img" aria-label={title}>
    <line x1={pad} y1={height - pad} x2={width - pad} y2={height - pad} stroke="#3f432d" stroke-width="1" />
    {#each values as value, index}
      {@const h = (Math.max(0, value) / maxValue) * (height - pad * 2)}
      <rect
        x={pad + index * barWidth + 2}
        y={height - pad - h}
        width={Math.max(2, barWidth - 4)}
        height={h}
        fill={color}
        opacity="0.88"
      />
    {/each}
  </svg>
  <div class="mt-2 flex justify-between text-xs text-muted-foreground">
    <span>{labels[0] ?? 'start'}</span>
    <span>{values.at(-1) !== undefined ? `${values.at(-1)?.toFixed(1)}${unit}` : 'No data'}</span>
    <span>{labels.at(-1) ?? 'latest'}</span>
  </div>
</div>
