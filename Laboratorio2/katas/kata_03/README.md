# Kata 03 — Empréstimos de ferramentas

Uma oficina registra retiradas e devoluções em um terminal sujeito a toques
duplicados e eventos inconsistentes. É preciso reconstruir os empréstimos válidos.

Implemente:

```python
resumir_emprestimos(eventos, fim_expediente)
```

Cada evento é `(minuto, ferramenta, pessoa, acao)`, com ação `"retirada"` ou
`"devolucao"`. A entrada pode estar fora de ordem e deve ser processada por minuto;
eventos no mesmo minuto preservam a ordem original.

Regras:

- uma retirada é válida somente quando a ferramenta está disponível;
- uma devolução é válida somente quando feita pela pessoa que está com a
  ferramenta;
- eventos inválidos são ignorados e contabilizados;
- empréstimos ainda abertos são encerrados em `fim_expediente`.

Retorne `(emprestimos, ignorados)`. Cada empréstimo é:

```text
(ferramenta, pessoa, inicio, fim, encerramento)
```

`encerramento` vale `"devolucao"` ou `"fim_expediente"`. Ordene os empréstimos por
início e depois por ferramenta. Lance `ValueError` para fim do expediente que não
seja inteiro não negativo, eventos malformados, minuto fora de `0..fim_expediente`,
campos de texto vazios ou ação desconhecida.

## Exemplo

```python
eventos = [
    (12, "furadeira", "ana", "devolucao"),
    (4, "furadeira", "ana", "retirada"),
    (7, "furadeira", "bia", "retirada"),  # ignorado: já emprestada
]

resumir_emprestimos(eventos, 20)
# ([("furadeira", "ana", 4, 12, "devolucao")], 1)
```

## Executar os testes

```bash
pytest katas/kata_03/tests -q
```

