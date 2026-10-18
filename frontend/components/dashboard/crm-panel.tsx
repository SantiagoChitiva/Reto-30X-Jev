"use client";

import { EmptyState, Notice } from "@/components/dashboard/notice";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { usePolling } from "@/hooks/use-polling";
import { getCrm } from "@/lib/api";
import {
  CONTENT_LABELS,
  SEGMENT_LABELS,
  formatP,
  formatTime,
  labelOf,
} from "@/lib/format";
import type { CrmRecord } from "@/lib/types";

const DECIDED_BY: Record<CrmRecord["decided_by"], string> = {
  jev: "JEV",
  jev_por_confirmar: "JEV, por confirmar",
  humano: "Persona",
};

export function CrmPanel() {
  const { data, error } = usePolling(
    (signal) => getCrm({ limit: 15, salesReady: true }, signal),
    2000,
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle>Listas para ventas en el CRM</CardTitle>
        <CardDescription>
          Lo que el equipo comercial ve en la ficha de cada persona: segmento,
          programa sugerido y quién lo decidió. Hoy es la tabla{" "}
          <span className="font-mono">crm_profiles</span>; con el CRM de 30X
          son las mismas propiedades.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {error && <Notice>No se pudo cargar el CRM: {error.message}.</Notice>}
        {data === undefined ? (
          !error && <EmptyState>Cargando fichas…</EmptyState>
        ) : data.length === 0 ? (
          <EmptyState>Todavía no hay personas listas para ventas.</EmptyState>
        ) : (
          <div className="max-h-[360px] overflow-auto rounded-lg border">
            <Table className="text-xs">
              <TableHeader className="sticky top-0 z-10 bg-card">
                <TableRow>
                  <TableHead>Actualizada</TableHead>
                  <TableHead>Persona</TableHead>
                  <TableHead>Segmento</TableHead>
                  <TableHead>Programa sugerido</TableHead>
                  <TableHead>Decidió</TableHead>
                  <TableHead className="text-right">Confianza</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.map((r) => (
                  <TableRow key={r.person_id}>
                    <TableCell className="text-muted-foreground">
                      {formatTime(r.updated_at)}
                    </TableCell>
                    <TableCell className="font-mono">{r.person_id}</TableCell>
                    <TableCell>{labelOf(SEGMENT_LABELS, r.segment)}</TableCell>
                    <TableCell>
                      {labelOf(CONTENT_LABELS, r.suggested_program)}
                    </TableCell>
                    <TableCell>{DECIDED_BY[r.decided_by]}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatP(r.confidence)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
