"use client";

import { useEffect, useRef, useState } from "react";
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
  anexarDocumento,
  baixarAnexo,
  buscarJuridico,
  confirmarJuridico,
  extrairJuridico,
  removerAnexo,
  type AchadoOnus,
  type AnexoOut,
  type Averbacao,
  type FichaJuridica,
  type JuridicoDocumental,
  type ProprietarioDoc,
  type TipoDocumento,
} from "@/lib/api";
import { me } from "@/lib/auth";

const TIPOS_ONUS = [
  "hipoteca",
  "alienacao_fiduciaria",
  "penhora",
  "arresto",
  "usufruto",
  "servidao",
  "inalienabilidade",
  "impenhorabilidade",
];

const TOM_NIVEL: Record<string, string> = {
  alto: "border-rose-200 bg-rose-50 text-rose-900",
  medio: "border-amber-200 bg-amber-50 text-amber-900",
  baixo: "border-emerald-200 bg-emerald-50 text-emerald-900",
};

// Ordem e rótulos das categorias do checklist (Fase 3.B — roteiro da advogada).
const CATEGORIAS_CHECKLIST: { chave: string; rotulo: string }[] = [
  { chave: "registro", rotulo: "Registro / requerimento" },
  { chave: "titulo", rotulo: "Título e cadeia dominial" },
  { chave: "tributarias", rotulo: "Certidões tributárias" },
  { chave: "distribuidores", rotulo: "Distribuidores cíveis/criminais" },
  { chave: "protesto", rotulo: "Protesto" },
  { chave: "aprovacao", rotulo: "Aprovação municipal/estadual" },
  { chave: "projeto", rotulo: "Projeto e instrumentos" },
  { chave: "observacao", rotulo: "Observações de triagem" },
];

export function CardJuridico({
  analiseId,
  onData,
  sinal,
}: {
  analiseId: string;
  onData?: (d: JuridicoDocumental) => void;
  sinal?: number;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [tipo, setTipo] = useState<TipoDocumento>("matricula");
  const [rascunho, setRascunho] = useState<FichaJuridica | null>(null);
  const [validadoPor, setValidadoPor] = useState("");
  const [resultado, setResultado] = useState<JuridicoDocumental | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function analisar() {
    setCarregando(true);
    setErro(null);
    try {
      const r = await buscarJuridico(analiseId);
      setResultado(r);
      onData?.(r);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao analisar.");
    } finally {
      setCarregando(false);
    }
  }

  // Ao abrir (ou trocar de análise), carrega o que JÁ está confirmado — para a lista de
  // matrículas já salvas aparecer mesmo antes de clicar em "Analisar".
  useEffect(() => {
    void analisar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analiseId]);

  // Pré-preenche "Validado por" com o usuário logado (continua editável; o gate humano
  // segue valendo — só tira o atrito de digitar o nome a cada matrícula).
  useEffect(() => {
    let vivo = true;
    me()
      .then((u) => {
        if (vivo) setValidadoPor((v) => v || u.nome || u.email);
      })
      .catch(() => {
        /* sem usuário → campo fica vazio (usuário digita) */
      });
    return () => {
      vivo = false;
    };
  }, []);

  // "Analisar tudo" (sinal) dispara a síntese (roda só com os alertas geo se não houver doc).
  const ultimoSinal = useRef(0);
  if (sinal && sinal !== ultimoSinal.current) {
    ultimoSinal.current = sinal;
    void analisar();
  }

  async function extrair(files: File[]) {
    if (files.length === 0) return;
    setCarregando(true);
    setErro(null);
    try {
      const f = await extrairJuridico(analiseId, files, tipo);
      setRascunho(f);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha na extração.");
    } finally {
      setCarregando(false);
    }
  }

  async function confirmar() {
    if (!rascunho) return;
    if (!validadoPor.trim()) {
      setErro("Informe quem está validando a ficha.");
      return;
    }
    setCarregando(true);
    setErro(null);
    try {
      await confirmarJuridico(analiseId, rascunho, validadoPor.trim());
      setRascunho(null);
      await analisar();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao confirmar.");
    } finally {
      setCarregando(false);
    }
  }

  function patch(p: Partial<FichaJuridica>) {
    setRascunho((r) => (r ? { ...r, ...p } : r));
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Jurídico — pré-análise documental</CardTitle>
        <CardDescription>
          Lê matrícula/certidões (LLM propõe com a referência ao ato) e sinaliza ônus,
          averbações e divergência de área. <strong>Pré-análise, não parecer</strong> — nada
          entra na síntese sem sua confirmação; ausência de achado não significa imóvel livre.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <Button onClick={analisar} disabled={carregando}>
            {carregando ? "Processando…" : "Analisar jurídico"}
          </Button>
          <span className="text-slate-300">·</span>
          <select
            value={tipo}
            onChange={(e) => setTipo(e.target.value as TipoDocumento)}
            className="rounded-lg border border-slate-200 px-2 py-2 text-sm"
          >
            <option value="matricula">Matrícula</option>
            <option value="certidao">Certidão</option>
          </select>
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,.jpg,.jpeg,.png,.webp,application/pdf,image/*"
            multiple
            className="hidden"
            onChange={(e) => {
              const fs = Array.from(e.target.files ?? []);
              if (fs.length) extrair(fs);
              e.target.value = "";
            }}
          />
          <Button
            className="bg-white text-slate-700 border border-slate-200 hover:bg-slate-50"
            onClick={() => inputRef.current?.click()}
            disabled={carregando}
          >
            Extrair documento (PDF/imagens)
          </Button>
        </div>
        <p className="-mt-2 text-[11px] text-slate-500">
          PDF ou imagens (JPEG/PNG). <strong>Uma</strong> matrícula por vez: selecione todas as
          páginas dela de uma vez (entram como um só documento), confirme, e repita para a
          próxima. Várias matrículas (ex.: gleba com 3 áreas) somam e aparecem todas na lista.
        </p>

        {erro && (
          <p className="rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{erro}</p>
        )}

        {resultado &&
          resultado.documentos.filter((d) => d.tipo === "matricula").length > 0 && (
            <div className="rounded-lg border border-emerald-200 bg-emerald-50/60 p-2.5 text-xs text-emerald-900">
              <span className="font-semibold">Matrículas já confirmadas: </span>
              {resultado.documentos
                .filter((d) => d.tipo === "matricula")
                .map((d, i) => (
                  <span
                    key={i}
                    className="mr-1 inline-block rounded-full bg-white px-2 py-0.5"
                  >
                    {d.matricula ? `Matrícula ${d.matricula}` : d.fonte ?? "documento"}
                    {d.area_m2 != null
                      ? ` · ${d.area_m2.toLocaleString("pt-BR")} m²`
                      : ""}
                  </span>
                ))}
              <span className="mt-1 block opacity-80">
                Carregue a próxima matrícula acima e <strong>confirme</strong> — cada uma
                soma à lista, não substitui.
              </span>
            </div>
          )}

        {rascunho && (
          <Revisao
            ficha={rascunho}
            validadoPor={validadoPor}
            setValidadoPor={setValidadoPor}
            patch={patch}
            onConfirmar={confirmar}
            onCancelar={() => setRascunho(null)}
            carregando={carregando}
          />
        )}

        {resultado && !rascunho && (
          <Resultado r={resultado} analiseId={analiseId} onChange={analisar} />
        )}
      </CardContent>
    </Card>
  );
}

/* ---------- Tela de revisão (propor → editar → confirmar) ---------- */
function Revisao({
  ficha,
  validadoPor,
  setValidadoPor,
  patch,
  onConfirmar,
  onCancelar,
  carregando,
}: {
  ficha: FichaJuridica;
  validadoPor: string;
  setValidadoPor: (v: string) => void;
  patch: (p: Partial<FichaJuridica>) => void;
  onConfirmar: () => void;
  onCancelar: () => void;
  carregando: boolean;
}) {
  function setOnus(i: number, p: Partial<AchadoOnus>) {
    patch({ onus: ficha.onus.map((o, k) => (k === i ? { ...o, ...p } : o)) });
  }
  function setAverb(i: number, p: Partial<Averbacao>) {
    patch({
      averbacoes: ficha.averbacoes.map((a, k) => (k === i ? { ...a, ...p } : a)),
    });
  }
  // Proprietários editáveis (gate humano sobre CPF/CNPJ, PF/PJ e atual/anterior).
  function setProp(i: number, p: Partial<ProprietarioDoc>) {
    if (!ficha.identificacao) return;
    const props = ficha.identificacao.proprietarios.map((pr, k) =>
      k === i ? { ...pr, ...p, origem: "editado_humano" as const } : pr,
    );
    patch({ identificacao: { ...ficha.identificacao, proprietarios: props } });
  }
  function addProp() {
    if (!ficha.identificacao) return;
    const novo: ProprietarioDoc = {
      nome: "",
      documento: null,
      tipo: null,
      situacao: "vigente",
      ato: null,
      pagina: null,
      trecho: null,
      origem: "editado_humano",
    };
    patch({
      identificacao: {
        ...ficha.identificacao,
        proprietarios: [...ficha.identificacao.proprietarios, novo],
      },
    });
  }
  function removeProp(i: number) {
    if (!ficha.identificacao) return;
    patch({
      identificacao: {
        ...ficha.identificacao,
        proprietarios: ficha.identificacao.proprietarios.filter((_, k) => k !== i),
      },
    });
  }

  return (
    <div className="space-y-4 rounded-xl border border-indigo-200 bg-indigo-50/40 p-4">
      <div className="flex items-center gap-2">
        <span className="rounded-full bg-indigo-200 px-2 py-0.5 text-[11px] font-semibold text-indigo-800">
          PROPOSTO PELO LLM
        </span>
        <span className="text-xs text-slate-500">
          {ficha.fonte_documento} · confira cada achado contra a referência ao ato.{" "}
          <strong className="text-indigo-700">
            Isto é só um rascunho — clique em “Confirmar” para SALVAR esta matrícula antes de
            carregar a próxima.
          </strong>
        </span>
      </div>

      {ficha.tipo === "matricula" ? (
        <>
          {ficha.identificacao && (
            <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
              <Campo
                rotulo="Matrícula"
                valor={ficha.identificacao.matricula?.valor ?? ""}
              />
              <Campo
                rotulo="Proprietário"
                valor={ficha.identificacao.proprietario_atual?.valor ?? ""}
              />
              <Campo
                rotulo="Cartório"
                valor={ficha.identificacao.cartorio?.valor ?? ""}
              />
              <Campo
                rotulo="Área registrada (m²)"
                valor={String(ficha.identificacao.area_registrada_m2?.valor ?? "")}
              />
            </div>
          )}

          {ficha.identificacao && (
            <div>
              <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
                Proprietários{" "}
                <span className="font-normal normal-case text-slate-400">
                  (confira CPF/CNPJ, PF/PJ e se é titular atual — alimenta o checklist)
                </span>
              </p>
              {ficha.identificacao.proprietarios.length === 0 && (
                <p className="text-xs text-slate-500">
                  Nenhum proprietário extraído — adicione manualmente abaixo.
                </p>
              )}
              <div className="space-y-2">
                {ficha.identificacao.proprietarios.map((p, i) => (
                  <div
                    key={i}
                    className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-white p-2"
                  >
                    <input
                      value={p.nome ?? ""}
                      onChange={(e) => setProp(i, { nome: e.target.value })}
                      placeholder="nome"
                      className="min-w-[12rem] flex-1 rounded border border-slate-200 px-2 py-1 text-xs"
                    />
                    <input
                      value={p.documento ?? ""}
                      onChange={(e) => setProp(i, { documento: e.target.value })}
                      placeholder="CPF / CNPJ"
                      className="w-40 rounded border border-slate-200 px-2 py-1 text-xs"
                    />
                    <select
                      value={p.tipo ?? ""}
                      onChange={(e) =>
                        setProp(i, {
                          tipo: (e.target.value || null) as "pf" | "pj" | null,
                        })
                      }
                      className="rounded border border-slate-200 px-1.5 py-1 text-xs"
                    >
                      <option value="">tipo</option>
                      <option value="pf">PF</option>
                      <option value="pj">PJ</option>
                    </select>
                    <select
                      value={p.situacao}
                      onChange={(e) =>
                        setProp(i, {
                          situacao: e.target.value as "vigente" | "anterior",
                        })
                      }
                      className="rounded border border-slate-200 px-1.5 py-1 text-xs"
                    >
                      <option value="vigente">atual</option>
                      <option value="anterior">anterior</option>
                    </select>
                    <button
                      onClick={() => removeProp(i)}
                      className="text-xs text-rose-600 hover:underline"
                    >
                      remover
                    </button>
                  </div>
                ))}
              </div>
              <button
                onClick={addProp}
                className="mt-1 text-xs font-medium text-indigo-700 hover:underline"
              >
                + adicionar proprietário
              </button>
            </div>
          )}

          <div>
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Ônus / gravames
            </p>
            {ficha.onus.length === 0 && (
              <p className="text-xs text-slate-500">
                Nenhum ônus proposto neste documento (não significa imóvel livre).
              </p>
            )}
            <div className="space-y-2">
              {ficha.onus.map((o, i) => (
                <div
                  key={i}
                  className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-white p-2"
                >
                  <select
                    value={o.tipo}
                    onChange={(e) => setOnus(i, { tipo: e.target.value })}
                    className="rounded border border-slate-200 px-1.5 py-1 text-xs"
                  >
                    {TIPOS_ONUS.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                  <input
                    value={o.descricao ?? ""}
                    onChange={(e) => setOnus(i, { descricao: e.target.value })}
                    placeholder="descrição"
                    className="min-w-[12rem] flex-1 rounded border border-slate-200 px-2 py-1 text-xs"
                  />
                  <input
                    value={o.ato ?? ""}
                    onChange={(e) => setOnus(i, { ato: e.target.value })}
                    placeholder="ato (R-5)"
                    className={`w-24 rounded border px-2 py-1 text-xs ${
                      o.ato ? "border-slate-200" : "border-rose-300 bg-rose-50"
                    }`}
                  />
                  <button
                    onClick={() =>
                      patch({ onus: ficha.onus.filter((_, k) => k !== i) })
                    }
                    className="text-xs text-slate-400 hover:text-rose-600"
                    title="remover"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          </div>

          {ficha.averbacoes.length > 0 && (
            <div>
              <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
                Averbações
              </p>
              <div className="space-y-2">
                {ficha.averbacoes.map((a, i) => (
                  <div
                    key={i}
                    className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-white p-2"
                  >
                    <input
                      value={a.tipo}
                      onChange={(e) => setAverb(i, { tipo: e.target.value })}
                      className="w-40 rounded border border-slate-200 px-2 py-1 text-xs"
                    />
                    <input
                      value={a.descricao ?? ""}
                      onChange={(e) => setAverb(i, { descricao: e.target.value })}
                      placeholder="descrição"
                      className="min-w-[10rem] flex-1 rounded border border-slate-200 px-2 py-1 text-xs"
                    />
                    <input
                      value={a.ato ?? ""}
                      onChange={(e) => setAverb(i, { ato: e.target.value })}
                      placeholder="ato (Av-3)"
                      className={`w-24 rounded border px-2 py-1 text-xs ${
                        a.ato ? "border-slate-200" : "border-rose-300 bg-rose-50"
                      }`}
                    />
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      ) : (
        <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-3">
          <Campo rotulo="Órgão" valor={ficha.orgao?.valor ?? ""} />
          <Campo rotulo="Espécie" valor={ficha.especie?.valor ?? ""} />
          <Campo rotulo="Resultado" valor={ficha.resultado ?? ""} />
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2 border-t border-indigo-200 pt-3">
        <input
          value={validadoPor}
          onChange={(e) => setValidadoPor(e.target.value)}
          placeholder="Validado por (seu nome)"
          className="rounded-lg border border-slate-200 px-2 py-2 text-sm"
        />
        <Button onClick={onConfirmar} disabled={carregando}>
          Confirmar ficha
        </Button>
        <button
          onClick={onCancelar}
          className="text-sm text-slate-500 hover:text-slate-800"
        >
          Descartar
        </button>
        <span className="ml-auto text-[11px] text-rose-600">
          Achado sem referência ao ato (campo vermelho) não é confirmável.
        </span>
      </div>
    </div>
  );
}

function Campo({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <div className="rounded-lg bg-white p-2">
      <p className="text-[11px] text-slate-500">{rotulo}</p>
      <p className="truncate text-sm font-medium text-slate-800">{valor || "—"}</p>
    </div>
  );
}

/* ---------- Ficha consolidada + síntese de risco ---------- */
function Resultado({
  r,
  analiseId,
  onChange,
}: {
  r: JuridicoDocumental;
  analiseId: string;
  onChange: () => void | Promise<void>;
}) {
  const s = r.sintese_risco;
  return (
    <div className="space-y-3">
      <div className={`rounded-xl border p-4 ${TOM_NIVEL[s.nivel]}`}>
        <div className="flex items-center gap-2">
          <span className="rounded-full bg-white/70 px-2 py-0.5 text-[11px] font-bold uppercase">
            risco {s.nivel}
          </span>
          <span className="text-sm font-medium">{s.resumo}</span>
        </div>
        {s.criticos.length > 0 && (
          <ul className="mt-2 space-y-0.5 text-xs">
            {s.criticos.map((c) => (
              <li key={c} className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-rose-500" /> {c}
              </li>
            ))}
          </ul>
        )}
        {s.atencao.length > 0 && (
          <ul className="mt-2 space-y-0.5 text-xs opacity-80">
            {s.atencao.map((c) => (
              <li key={c} className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-amber-500" /> {c}
              </li>
            ))}
          </ul>
        )}
      </div>

      {r.documentos.length > 0 && (
        <div>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
            Documentos analisados{" "}
            {r.documentos.filter((d) => d.tipo === "matricula").length > 1 &&
              `· ${r.documentos.filter((d) => d.tipo === "matricula").length} matrículas`}
          </p>
          <ul className="space-y-1">
            {r.documentos.map((d, i) => (
              <li
                key={i}
                className="flex flex-wrap items-center gap-x-2 gap-y-0.5 rounded-lg border border-slate-200 bg-slate-50 p-2 text-sm"
              >
                <span className="rounded-full bg-slate-200 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-slate-600">
                  {d.tipo}
                </span>
                {d.matricula && (
                  <span className="font-medium">Matrícula {d.matricula}</span>
                )}
                {d.proprietario && (
                  <span className="text-slate-600">· {d.proprietario}</span>
                )}
                {d.area_m2 != null && (
                  <span className="text-slate-600">
                    · {d.area_m2.toLocaleString("pt-BR")} m²
                  </span>
                )}
                {d.fonte && (
                  <span className="text-xs text-slate-400">· {d.fonte}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {r.area_check && (
        <div className="rounded-xl border border-slate-200 p-3 text-sm">
          <span className="font-medium">Área:</span>{" "}
          {r.area_check.n_matriculas > 1
            ? `soma de ${r.area_check.n_matriculas} matrículas `
            : "matrícula "}
          {r.area_check.area_matricula_m2?.toLocaleString("pt-BR") ?? "—"} m² × KMZ{" "}
          {r.area_check.area_kmz_m2.toLocaleString("pt-BR")} m² ·{" "}
          <span
            className={
              r.area_check.status === "conforme"
                ? "text-emerald-700"
                : r.area_check.status === "atencao"
                  ? "text-rose-700"
                  : "text-slate-500"
            }
          >
            {r.area_check.status}
            {r.area_check.divergencia_pct != null &&
              ` (${(r.area_check.divergencia_pct * 100).toLocaleString("pt-BR", {
                maximumFractionDigits: 1,
              })}%)`}
          </span>
        </div>
      )}

      {r.onus.length > 0 && (
        <div>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
            Ônus / gravames
          </p>
          <ul className="space-y-1">
            {r.onus.map((o, i) => {
              const ativo = o.situacao === "consta";
              return (
                <li
                  key={i}
                  className={`rounded-lg border p-2 text-sm ${
                    ativo
                      ? "border-amber-200 bg-amber-50"
                      : "border-slate-200 bg-slate-50 opacity-60"
                  }`}
                >
                  <span className="font-medium">{o.tipo}</span>
                  <span
                    className={`ml-1.5 rounded-full px-1.5 py-0.5 text-[10px] font-semibold uppercase ${
                      ativo
                        ? "bg-amber-200 text-amber-900"
                        : "bg-slate-200 text-slate-600"
                    }`}
                  >
                    {ativo ? "ativo" : o.situacao}
                  </span>
                  {o.descricao ? ` — ${o.descricao}` : ""}{" "}
                  <span className="text-xs text-slate-500">· {o.proveniencia}</span>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {r.averbacoes.length > 0 && (
        <div>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
            Averbações registradas <span className="font-normal">(histórico)</span>
          </p>
          <ul className="space-y-1">
            {r.averbacoes.map((a, i) => (
              <li key={i} className="text-xs text-slate-600">
                <span className="font-medium text-slate-700">{a.tipo}</span>
                {a.descricao ? ` — ${a.descricao}` : ""}{" "}
                <span className="text-slate-400">· {a.proveniencia}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {r.certidoes.length > 0 && (
        <ul className="space-y-1">
          {r.certidoes.map((c, i) => (
            <li key={i} className="text-sm text-slate-700">
              {c.orgao} — {c.resultado}{" "}
              <span
                className={
                  c.status === "atencao" ? "text-rose-700" : "text-emerald-700"
                }
              >
                ({c.status})
              </span>
            </li>
          ))}
        </ul>
      )}

      {r.proprietarios.length > 0 && (
        <div>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
            Proprietários (das matrículas)
          </p>
          <ul className="space-y-1">
            {r.proprietarios.map((p, i) => (
              <li
                key={i}
                className="flex flex-wrap items-center gap-x-2 rounded-lg border border-slate-200 bg-slate-50 p-2 text-sm"
              >
                {p.tipo && (
                  <span className="rounded-full bg-slate-200 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-slate-600">
                    {p.tipo}
                  </span>
                )}
                {!p.vigente && (
                  <span className="rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-amber-700">
                    anterior
                  </span>
                )}
                <span className="font-medium">{p.nome ?? "(sem nome)"}</span>
                {p.documento && (
                  <span className="text-slate-600">· {p.documento}</span>
                )}
                {p.matriculas.length > 0 && (
                  <span className="text-xs text-slate-400">
                    · matrícula(s) {p.matriculas.join(", ")}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {r.checklist.length > 0 && (
        <div>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
            Checklist de documentos (roteiro)
          </p>
          <p className="mb-2 text-[11px] text-slate-500">
            Gerado a partir dos proprietários e da jurisdição.{" "}
            <strong>Triagem, não parecer.</strong>{" "}
            <span className="rounded bg-indigo-100 px-1 text-indigo-700">auto</span> = poderá
            ser baixado por CPF/CNPJ (Fase C).
          </p>
          <div className="space-y-3">
            {CATEGORIAS_CHECKLIST.filter((c) =>
              r.checklist.some((i) => i.categoria === c.chave),
            ).map((c) => (
              <div key={c.chave}>
                <p className="mb-1 text-[11px] font-semibold text-slate-600">
                  {c.rotulo}
                </p>
                <ul className="space-y-1">
                  {r.checklist
                    .filter((i) => i.categoria === c.chave)
                    .map((i) => (
                      <li
                        key={i.chave}
                        className="rounded-lg border border-slate-200 p-2 text-sm"
                      >
                        <div className="flex flex-wrap items-center gap-1.5">
                          <span
                            className={`h-2 w-2 rounded-full ${
                              i.status === "anexado"
                                ? "bg-emerald-500"
                                : "bg-slate-300"
                            }`}
                          />
                          <span className="font-medium">{i.titulo}</span>
                          {!i.obrigatorio && (
                            <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-500">
                              condicional
                            </span>
                          )}
                          {i.auto_disponivel && (
                            <span className="rounded-full bg-indigo-100 px-1.5 py-0.5 text-[10px] font-semibold text-indigo-700">
                              auto
                            </span>
                          )}
                        </div>
                        {i.em_nome_de.length > 0 && (
                          <p className="mt-0.5 text-xs text-slate-600">
                            Em nome de: {i.em_nome_de.join("; ")}
                          </p>
                        )}
                        {i.condicional && (
                          <p className="text-xs text-amber-700">Aplica {i.condicional}</p>
                        )}
                        {i.observacao && (
                          <p className="text-xs text-slate-500">{i.observacao}</p>
                        )}
                        {i.fonte_legal && (
                          <p className="text-[10px] text-slate-400">{i.fonte_legal}</p>
                        )}
                        <ItemAnexos
                          analiseId={analiseId}
                          chave={i.chave}
                          anexos={i.anexos}
                          onChange={onChange}
                        />
                      </li>
                    ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}

      <Notas itens={r.avisos} />
    </div>
  );
}

/* ---------- Anexos de um item do checklist (Fase 3.C manual) ---------- */
function ItemAnexos({
  analiseId,
  chave,
  anexos,
  onChange,
}: {
  analiseId: string;
  chave: string;
  anexos: AnexoOut[];
  onChange: () => void | Promise<void>;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [ocupado, setOcupado] = useState(false);

  async function anexar(arquivo: File) {
    setOcupado(true);
    try {
      await anexarDocumento(analiseId, chave, arquivo);
      await onChange();
    } finally {
      setOcupado(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }
  async function remover(id: string) {
    setOcupado(true);
    try {
      await removerAnexo(analiseId, id);
      await onChange();
    } finally {
      setOcupado(false);
    }
  }
  async function baixar(a: AnexoOut) {
    const blob = await baixarAnexo(analiseId, a.id);
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = a.fonte_documento;
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="mt-1.5 border-t border-dashed border-slate-200 pt-1.5">
      {anexos.map((a) => (
        <div key={a.id} className="flex items-center gap-2 text-xs text-slate-600">
          <span className="text-emerald-600">✓</span>
          <button onClick={() => baixar(a)} className="truncate text-indigo-700 hover:underline">
            {a.fonte_documento}
          </button>
          <span className="text-slate-400">
            ({Math.max(1, Math.round(a.tamanho_bytes / 1024))} KB)
          </span>
          <button
            onClick={() => remover(a.id)}
            disabled={ocupado}
            className="text-rose-600 hover:underline disabled:opacity-50"
          >
            remover
          </button>
        </div>
      ))}
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf,image/*"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) void anexar(f);
        }}
      />
      <button
        onClick={() => inputRef.current?.click()}
        disabled={ocupado}
        className="mt-0.5 text-xs font-medium text-slate-600 hover:text-indigo-700 disabled:opacity-50"
      >
        {ocupado ? "enviando…" : "+ anexar documento"}
      </button>
    </div>
  );
}
