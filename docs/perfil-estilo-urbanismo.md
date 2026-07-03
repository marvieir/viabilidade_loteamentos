# Perfil de ESTILO do urbanismo (Movimento 2) — a "skill" do operador

O gerador e o motor leem, em TODA proposta, um conjunto de regras por padrão
(`baixa` / `media` / `alta`). Os **defaults** estão versionados no código
(`backend/app/core/urbanismo_estilo.py`) e reproduzem o comportamento testado.

## Como sobrescrever (sem rebuild)

Crie `{perfil}.json` no diretório do volume `ESTILO_URBANISMO_DIR`
(`/data/perfis/estilo-urbanismo` nos composes). Exemplo — `alta.json`:

```json
{
  "prompt_regras": "Lazer espalhado em estações pequenas; lago estruturador; traçado sinuoso com vistas; verde conectando os setores; entrada com parkway.",
  "pracas_por_quadras": 8,
  "lazer_pracas_frac": 0.4,
  "lago_prioritario": true,
  "lago_frac_aproveitavel": 0.04,
  "lago_max_m2": 15000,
  "hub_fracao_livre": 0.3
}
```

| Chave | Efeito |
|---|---|
| `prompt_regras` | texto que entra no prompt do PROGRAMA em toda geração (estilo/caráter) |
| `pracas_por_quadras` | piso de praças: 1 a cada N quadras mesmo com cobertura de 400 m ok (0 = só cobertura) |
| `lazer_pracas_frac` | teto do orçamento de lazer que pode virar praça de bolso |
| `lago_prioritario` | `true` = lago sacrifica lotes (redimensiona p/ a quadra disponível) |
| `lago_frac_aproveitavel` / `lago_max_m2` | dimensão de triagem do lago |
| `hub_fracao_livre` | fração do clube preservada como jardins/circulação |

Regras: arquivo inválido → default + aviso na proposta (nunca derruba); knob
não-numérico → default daquele knob; nenhum número de MEDIDA vem daqui (§2).

No container (produção/dev com podman):
```
podman-compose exec api sh -c 'mkdir -p /data/perfis/estilo-urbanismo && cat > /data/perfis/estilo-urbanismo/alta.json' < alta.json
```
(ou monte o arquivo pelo host no volume `perfis_dados`). Depois é só REGENERAR
o estudo — não precisa reiniciar o serviço (o estilo é lido a cada geração).
