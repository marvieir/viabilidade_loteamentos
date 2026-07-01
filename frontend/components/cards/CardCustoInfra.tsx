"use client";

import { useEffect, useState } from "react";
import { StatusChip } from "@/components/ui/status";
import { Notas } from "@/components/ui/notas";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  calcularCustoInfra,
  obterPerfilCustos,
  salvarPerfilCustos,
  type CustoInfra,
  type PerfilCustos,
} from "@/lib/api";

/* Tier 3 — Motor de custo de infraestrutura (paramétrico por disciplina).
   O front SÓ renderiza/coleta: o operador preenche a tabela de custos (perfil), e o backend
   multiplica pelas quantidades do layout de Urbanismo. Nenhum número é calculado aqui (§2).
   Indexado por padrão (econômico/médio/alto). Degrada honesto se o perfil não estiver preenchido. */

type LinhaEdit = {
  chave: string;
  rotulo: string;
  base: string;
  base_rotulo: string;
  ancora: string;
  bases: { chave: string; rotulo: string }[];
  eco: string;
  med: string;
  alt: string;
};

const PADRAO_COR: Record<string, string> = {
  COMPLETA: "bg-emerald-50 text-emerald-700 border-emerald-200",
  PARCIAL: "bg-amber-50 text-amber-700 border-amber-200",
  INDISPONIVEL: "bg-slate-100 text-slate-600 border-slate-200",
};

const s = (v: number | null | undefined) => (v == null ? "" : String(v));
const parseNum = (t: string): number | null => {
  const x = t.trim().replace(/\./g, "").replace(",", ".");
  if (!x) return null;
  const n = Number(x);
  return Number.isFinite(n) ? n : null;
};

export function CardCustoInfra({
  analiseId,
  onData,
  sinal,
}: {
  analiseId: string;
  onData?: (d: CustoInfra | null) => void;
  sinal?: number;
}) {
  const [perfil, setPerfil] = useState<PerfilCustos | null>(null);
  const [linhas, setLinhas] = useState<LinhaEdit[]>([]);
  const [bdi, setBdi] = useState("0");
  const [dataRef, setDataRef] = useState("");
  const [uf, setUf] = useState("");
  const [fonte, setFonte] = useState("perfil do operador");
  const [padrao, setPadrao] = useState("medio");
  const [resultado, setResultado] = useState<CustoInfra | null>(null);
  const [editando, setEditando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);
  const [calculando, setCalculando] = useState(false);

  function popular(p: PerfilCustos) {
    setPerfil(p);
    setBdi(s(p.bdi_pct));
    setDataRef(p.data_referencia ?? "");
    setUf(p.uf ?? "");
    setFonte(p.fonte ?? "perfil do operador");
    setLinhas(
      p.disciplinas.map((d) => ({
        chave: d.chave,
        rotulo: d.rotulo,
        base: d.base,
        base_rotulo: d.base_rotulo,
        ancora: d.ancora,
        bases: d.bases_disponiveis,
        eco: s(d.custo_economico),
        med: s(d.custo_medio),
        alt: s(d.custo_alto),
      }))
    );
    setEditando(!p.configurado); // abre o editor se ainda não preenchido
  }

  async function carregarPerfil() {
    setErro(null);
    try {
      popular(await obterPerfilCustos());
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao carregar o perfil de custos.");
    }
  }

  useEffect(() => {
    carregarPerfil();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (sinal) calcular();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sinal]);

  function setCampo(i: number, campo: "eco" | "med" | "alt" | "base", valor: string) {
    setLinhas((ls) => ls.map((l, j) => (j === i ? { ...l, [campo]: valor } : l)));
  }

  async function salvar() {
    setSalvando(true);
    setErro(null);
    try {
      const p = await salvarPerfilCustos({
        bdi_pct: parseNum(bdi) ?? 0,
        data_referencia: dataRef || null,
        uf: uf || null,
        fonte: fonte || null,
        disciplinas: linhas.map((l) => ({
          chave: l.chave,
          base: l.base,
          custo_economico: parseNum(l.eco),
          custo_medio: parseNum(l.med),
          custo_alto: parseNum(l.alt),
        })),
      });
      popular(p);
      setEditando(false);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao salvar a tabela de custos.");
    } finally {
      setSalvando(false);
    }
  }

  async function calcular() {
    setCalculando(true);
    setErro(null);
    try {
      const r = await calcularCustoInfra(analiseId, padrao);
      setResultado(r);
      onData?.(r);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao calcular o custo.");
    } finally {
      setCalculando(false);
    }
  }

  const isPct = (chave: string) => chave === "canteiro";

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">
          <span>Custo de Infraestrutura</span>
          {resultado ? (
            resultado.cobertura === "COMPLETA" ? (
              <StatusChip className="ml-auto" estado="ok" rotulo="calculado" />
            ) : resultado.cobertura === "PARCIAL" ? (
              <StatusChip className="ml-auto" estado="atencao" rotulo="parcial" />
            ) : (
              <StatusChip className="ml-auto" estado="atencao" rotulo="sem custos" />
            )
          ) : (
            <StatusChip className="ml-auto" estado="pendente" />
          )}
        </CardTitle>
        <CardDescription>
          Estimativa paramétrica por disciplina: as <span className="font-medium">quantidades</span>{" "}
          vêm do layout de Urbanismo e os <span className="font-medium">custos unitários</span> vêm
          da sua tabela (perfil do operador), por padrão (econômico/médio/alto). Triagem — cada
          número carrega proveniência; sem custo preenchido, não há estimativa (degrada honesto).
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {erro && (
          <p className="rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{erro}</p>
        )}

        {/* ---- Tabela de custos (perfil do operador) ---- */}
        <div className="rounded-lg border border-slate-200">
          <button
            onClick={() => setEditando((v) => !v)}
            className="flex w-full items-center justify-between px-3 py-2 text-sm font-medium text-slate-800"
          >
            <span>
              Tabela de custos (perfil do operador)
              {perfil && !perfil.configurado && (
                <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800">
                  não preenchida
                </span>
              )}
            </span>
            <span className="text-xs text-slate-500">{editando ? "fechar ▲" : "editar ▼"}</span>
          </button>

          {editando && (
            <div className="space-y-3 border-t border-slate-200 p-3">
              <p className="text-xs text-slate-500">
                Informe o custo unitário por disciplina (em R$; canteiro em %). Use ponto ou vírgula
                para decimais, sem separador de milhar. Deixe em branco o que não se aplica.
              </p>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-left text-slate-500">
                      <th className="py-1 pr-2">Disciplina</th>
                      <th className="py-1 pr-2">Base de cálculo</th>
                      <th className="py-1 pr-2">Econômico</th>
                      <th className="py-1 pr-2">Médio</th>
                      <th className="py-1 pr-2">Alto</th>
                    </tr>
                  </thead>
                  <tbody>
                    {linhas.map((l, i) => (
                      <tr key={l.chave} className="border-t border-slate-100">
                        <td className="py-1.5 pr-2">
                          <span className="font-medium text-slate-800">{l.rotulo}</span>
                          <span className="ml-1 text-[10px] text-slate-400">{l.ancora}</span>
                        </td>
                        <td className="py-1.5 pr-2">
                          {l.bases.length > 1 ? (
                            <select
                              value={l.base}
                              onChange={(e) => setCampo(i, "base", e.target.value)}
                              className="rounded border border-slate-200 bg-white px-1 py-0.5 text-xs"
                            >
                              {l.bases.map((b) => (
                                <option key={b.chave} value={b.chave}>
                                  {b.rotulo}
                                </option>
                              ))}
                            </select>
                          ) : (
                            <span className="text-slate-500">{l.base_rotulo}</span>
                          )}
                        </td>
                        {(["eco", "med", "alt"] as const).map((c) => (
                          <td key={c} className="py-1.5 pr-2">
                            <div className="flex items-center gap-1">
                              <span className="text-slate-400">{isPct(l.chave) ? "%" : "R$"}</span>
                              <input
                                value={l[c]}
                                onChange={(e) => setCampo(i, c, e.target.value)}
                                inputMode="decimal"
                                placeholder="—"
                                className="w-20 rounded border border-slate-200 px-1.5 py-0.5 text-xs"
                              />
                            </div>
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <label className="text-xs text-slate-600">
                  BDI (%)
                  <input
                    value={bdi}
                    onChange={(e) => setBdi(e.target.value)}
                    inputMode="decimal"
                    className="mt-0.5 w-full rounded border border-slate-200 px-2 py-1 text-sm"
                  />
                </label>
                <label className="text-xs text-slate-600">
                  Mês de referência
                  <input
                    value={dataRef}
                    onChange={(e) => setDataRef(e.target.value)}
                    placeholder="2026-06"
                    className="mt-0.5 w-full rounded border border-slate-200 px-2 py-1 text-sm"
                  />
                </label>
                <label className="text-xs text-slate-600">
                  UF
                  <input
                    value={uf}
                    onChange={(e) => setUf(e.target.value)}
                    placeholder="SP"
                    className="mt-0.5 w-full rounded border border-slate-200 px-2 py-1 text-sm"
                  />
                </label>
                <label className="text-xs text-slate-600">
                  Fonte (proveniência)
                  <input
                    value={fonte}
                    onChange={(e) => setFonte(e.target.value)}
                    className="mt-0.5 w-full rounded border border-slate-200 px-2 py-1 text-sm"
                  />
                </label>
              </div>

              <Button onClick={salvar} disabled={salvando}>
                {salvando ? "Salvando…" : "Salvar tabela de custos"}
              </Button>
            </div>
          )}
        </div>

        {/* ---- Calcular ---- */}
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm text-slate-600">Padrão do loteamento:</span>
          {(perfil?.padroes ?? []).map((p) => (
            <button
              key={p.chave}
              onClick={() => setPadrao(p.chave)}
              className={`rounded-full border px-3 py-1 text-xs font-medium ${
                padrao === p.chave
                  ? "border-slate-800 bg-slate-800 text-white"
                  : "border-slate-200 bg-white text-slate-600"
              }`}
            >
              {p.rotulo}
            </button>
          ))}
          <Button onClick={calcular} disabled={calculando}>
            {calculando ? "Calculando…" : "Calcular custo"}
          </Button>
        </div>

        {resultado && <Resultado r={resultado} />}
      </CardContent>
    </Card>
  );
}

function Resultado({ r }: { r: CustoInfra }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <span className="text-sm font-semibold text-slate-900">
          Custo de infraestrutura — padrão {r.padrao_rotulo}
        </span>
        <span
          className={`rounded-full border px-2 py-0.5 text-xs font-medium ${
            PADRAO_COR[r.cobertura] ?? PADRAO_COR.INDISPONIVEL
          }`}
        >
          {r.cobertura === "COMPLETA"
            ? "todas as disciplinas"
            : r.cobertura === "PARCIAL"
            ? "parcial"
            : "sem dado de custo"}
        </span>
      </div>

      {r.cobertura === "INDISPONIVEL" ? (
        <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
          Preencha a tabela de custos (acima) para este padrão — nada é estimado sem os custos
          unitários do operador.
        </p>
      ) : (
        <>
          <div className="overflow-x-auto rounded-lg border border-slate-200">
            <table className="w-full text-xs">
              <thead className="bg-slate-50 text-left text-slate-500">
                <tr>
                  <th className="px-2 py-1.5">Disciplina</th>
                  <th className="px-2 py-1.5">Quantidade</th>
                  <th className="px-2 py-1.5">Unitário</th>
                  <th className="px-2 py-1.5 text-right">Subtotal</th>
                </tr>
              </thead>
              <tbody>
                {r.disciplinas.map((d) => (
                  <tr key={d.chave} className="border-t border-slate-100">
                    <td className="px-2 py-1.5">
                      <span className={d.preenchido ? "text-slate-800" : "text-slate-400"}>
                        {d.rotulo}
                      </span>
                      {d.aviso && (
                        <span className="ml-1 text-[10px] text-amber-600">⚠ {d.aviso}</span>
                      )}
                    </td>
                    <td className="px-2 py-1.5 text-slate-600">{d.quantidade_fmt ?? "—"}</td>
                    <td className="px-2 py-1.5 text-slate-600">{d.custo_unitario_fmt ?? "—"}</td>
                    <td className="px-2 py-1.5 text-right font-medium text-slate-900">
                      {d.subtotal_fmt ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="border-t border-slate-200 text-slate-700">
                <tr>
                  <td className="px-2 py-1.5" colSpan={3}>
                    Subtotal direto
                  </td>
                  <td className="px-2 py-1.5 text-right">{r.subtotal_direto_fmt ?? "—"}</td>
                </tr>
                <tr>
                  <td className="px-2 py-1.5" colSpan={3}>
                    BDI ({r.bdi_pct.toLocaleString("pt-BR")}%)
                  </td>
                  <td className="px-2 py-1.5 text-right">{r.bdi_valor_fmt ?? "—"}</td>
                </tr>
                <tr className="bg-slate-50 font-semibold text-slate-900">
                  <td className="px-2 py-2" colSpan={3}>
                    Custo total da infraestrutura
                  </td>
                  <td className="px-2 py-2 text-right">{r.total_fmt ?? "—"}</td>
                </tr>
              </tfoot>
            </table>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
              <p className="text-xs text-slate-500">Custo por lote</p>
              <p className="text-base font-semibold text-slate-900">
                {r.custo_por_lote_fmt ?? "—"}
              </p>
            </div>
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
              <p className="text-xs text-slate-500">Custo por m² urbanizado</p>
              <p className="text-base font-semibold text-slate-900">{r.custo_por_m2_fmt ?? "—"}</p>
            </div>
          </div>
        </>
      )}

      <p className="text-xs text-slate-500">{r.proveniencia}</p>
      <Notas itens={r.avisos} />
    </div>
  );
}
