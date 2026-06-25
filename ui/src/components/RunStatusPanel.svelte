<script lang="ts">
  import Metric from "./Metric.svelte";
  import type { RunStatusResponse } from "../commands/runhaven";

  export let runStatus: RunStatusResponse | null;
  export let runStatusLoading: boolean;
  export let runStatusError: string;
  export let controlBusy: boolean;
  export let controlError: string;
  export let controlMessage: string;
  export let onStop: () => void;
  export let onKill: () => void;
  export let onRepair: () => void;

  let stopConfirmed = false;
  let killConfirmed = false;
  let repairConfirmed = false;

  function formatMemory(bytes: number | null): string {
    if (bytes === null) {
      return "unknown";
    }
    return `${Math.round(bytes / 1024 ** 2)} MiB`;
  }
</script>

<section class="panel run-status-panel" aria-live="polite">
  <h2>Run status</h2>
  {#if runStatusLoading}
    <p class="muted">Refreshing status...</p>
  {:else if runStatus}
    <dl class="plan-grid">
      <Metric label="Marker status" value={runStatus.run.status} />
      <Metric label="Container state" value={runStatus.container.state} />
      <Metric label="Image" value={runStatus.container.image ?? "-"} />
      <Metric label="Started" value={runStatus.container.startedAt ?? "-"} />
      <Metric label="CPU" value={runStatus.container.resources.cpus ?? "unknown"} />
      <Metric label="Memory" value={formatMemory(runStatus.container.resources.memoryBytes)} />
    </dl>
    {#if runStatus.container.networks.length > 0}
      <div class="status-list">
        {#each runStatus.container.networks as network}
          <p>
            {network.network ?? "network"}
            {#if network.ipv4Address}
              <span>ipv4={network.ipv4Address}</span>
            {/if}
            {#if network.hostname}
              <span>host={network.hostname}</span>
            {/if}
          </p>
        {/each}
      </div>
    {/if}
  {:else if runStatusError}
    <p class="notice">{runStatusError}</p>
  {/if}

  {#if runStatus}
    <div class="run-control">
      <label class="choice">
        <input type="checkbox" bind:checked={stopConfirmed} />
        <span>Confirm stopping this run.</span>
      </label>
      <button class="secondary" type="button" disabled={!stopConfirmed || controlBusy} on:click={onStop}>
        <span>Stop run</span>
      </button>

      <label class="choice">
        <input type="checkbox" bind:checked={killConfirmed} />
        <span>Confirm hard-stopping this run.</span>
      </label>
      <button class="secondary" type="button" disabled={!killConfirmed || controlBusy} on:click={onKill}>
        <span>Hard stop</span>
      </button>

      <label class="choice">
        <input type="checkbox" bind:checked={repairConfirmed} />
        <span>Confirm clearing this run's stale marker.</span>
      </label>
      <button class="secondary" type="button" disabled={!repairConfirmed || controlBusy} on:click={onRepair}>
        <span>Repair marker</span>
      </button>

      {#if controlMessage}
        <p class="notice success" role="status">{controlMessage}</p>
      {/if}
      {#if controlError}
        <p class="notice" role="alert">{controlError}</p>
      {/if}
    </div>
  {/if}
</section>
