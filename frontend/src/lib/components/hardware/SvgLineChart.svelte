<script lang="ts">
  export let values: number[] = [];
  export let labels: string[] = [];
  export let yMax: number | null = null;
  export let color = '#d8ff00';
  export let unit = '';
  export let title = 'Chart';

  const width = 640;
  const height = 180;
  const pad = 18;

  $: maxValue = yMax ?? Math.max(1, ...values);
  $: points = values.map((value, index) => {
    const x = values.length <= 1 ? pad : pad + (index / (values.length - 1)) * (width - pad * 2);
    const y = height - pad - (Math.max(0, value) / maxValue) * (height - pad * 2);
    return `${x},${y}`;
  }).join(' ');
  $: latest = values.at(-1);
</script>

<div class="relative">
  <svg class="h-48 w-full" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" role="img" aria-label={title}>
    <line x1={pad} y1={height - pad} x2={width - pad} y2={height - pad} stroke="#3f432d" stroke-width="1" />
    <line x1={pad} y1={pad} x2={pad} y2={height - pad} stroke="#3f432d" stroke-width="1" />
    {#if values.length > 1}
      <polyline points={points} fill="none" stroke={color} stroke-width="2.5" vector-effect="non-scaling-stroke" />
    {/if}
  </svg>
  <div class="mt-2 flex justify-between text-xs text-muted-foreground">
    <span>{labels[0] ?? 'start'}</span>
    <span>{latest !== undefined ? `${latest.toFixed(1)}${unit}` : 'No data'}</span>
    <span>{labels.at(-1) ?? 'now'}</span>
  </div>
</div>
