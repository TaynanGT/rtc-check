# Mensagens prontas

Escritas para serem enviadas por **você**, no seu nome, uma a uma. Não são template
de disparo em massa — cada uma tem um `[colchete]` que precisa ser preenchido com
algo específico daquela empresa. Se você não consegue preencher, não mande: significa
que não pesquisou o suficiente e a pessoa vai perceber.

Todas as afirmações abaixo são verdadeiras hoje. Não diga nada além disso.

---

## 1. Escritório contábil (e-mail frio)

**Assunto:** seus clientes em Lucro Real estão prontos pro dia 3?

> Oi, [nome],
>
> Vi que vocês atendem [tipo de cliente — indústria, distribuidora, o que for
> verificável no site deles].
>
> Dia 3 de agosto o SEFAZ começa a rejeitar NF-e de emitente CRT=3 sem os campos de
> IBS e CBS. Você já deve estar cuidando disso. A parte chata não é a regra, é
> descobrir quais produtos do cadastro de cada cliente estão fora.
>
> Fiz uma ferramenta que lê a pasta de XML que o cliente já tem e devolve a lista de
> SKUs que precisam de ação, agrupada por produto. Um SKU que aparece em 4.000 notas
> vira uma linha, não quatro mil.
>
> Roda na máquina, nada sobe pra lugar nenhum — imagino que mandar XML de cliente pra
> servidor de terceiro não seja uma opção pra vocês. É gratuita e de código aberto:
> [link]
>
> Se rodar e não servir, me diz o que faltou. É a informação que eu mais preciso agora.
>
> [seu nome]

Por que funciona: reconhece que a pessoa já sabe do problema (não a trata como leiga),
nomeia a dor real (descobrir *quais*), antecipa a objeção de privacidade, e pede
feedback em vez de reunião.

---

## 2. Parceiro de infraestrutura fiscal (TecnoSpeed, Focus, NFE.io e afins)

**Assunto:** ferramenta aberta de auditoria prévia — encaixa antes da emissão de vocês

> Oi, [nome ou "time da [empresa]"],
>
> Vocês cuidam da emissão. Fiz uma coisa que fica um passo antes: um CLI aberto que
> varre o acervo de XML do cliente e aponta quais itens vão ser rejeitados a partir de
> 3 de agosto por falta de gIBSCBS/cClassTrib.
>
> O motivo de eu escrever: [algo específico e verificável — "vocês publicaram um
> material sobre preparar ISVs pra Reforma", "o posicionamento de vocês é economizar
> tempo de dev do cliente"]. Isso é o mesmo problema, uma etapa antes.
>
> Não é concorrente de vocês, é o oposto: cliente que limpa o cadastro antes gera menos
> rejeição na API e menos ticket no suporte de vocês.
>
> É AGPL, roda local, zero dependência: [link]
>
> Faz sentido conversar sobre indicação nos dois sentidos? Sem pressa nenhuma, sei que
> agosto está pegando pra todo mundo aí.
>
> [seu nome]

Por que funciona: chega como complemento, não como pedido. O argumento de "menos ticket
de suporte" é interesse deles, não seu. E fecha reconhecendo o momento — quem trabalha
com fiscal está afogado agora, e fingir que não está soa falso.

---

## 3. Post em comunidade (LinkedIn, grupo de fiscal)

> Faltam [N] dias pro dia 3 de agosto, quando o SEFAZ passa a rejeitar NF-e de CRT=3
> sem IBS e CBS.
>
> Todo mundo já entendeu a regra. O problema que ninguém resolveu é operacional: você
> tem 4.000 notas no disco e não sabe quais dos seus produtos estão fora.
>
> Escrevi um programinha que lê essa pasta e responde isso. Ele agrupa por SKU, que é
> como o trabalho realmente acontece — o mesmo produto quebrado em 4.000 notas é uma
> correção de cadastro, não quatro mil.
>
> Roda na sua máquina, não sobe nada pra lugar nenhum, é aberto e é de graça: [link]
>
> [print da saída do terminal]
>
> Se rodar aí e o número vier estranho, me manda. Falso positivo é o que eu mais quero
> caçar agora.

Por que funciona: começa pela urgência compartilhada, mostra o resultado em vez de
descrever, e o pedido final é de ajuda, não de venda.

---

## 4. Show HN / post em inglês

**Título:** Show HN: Scan your Brazilian e-invoice archive for a tax-reform deadline

> Brazil is mid tax reform. On Aug 3 the tax authority starts rejecting e-invoices
> that lack the new IBS/CBS fields, for companies on the regular tax regime.
>
> The rule is simple. Finding which of your thousands of product records are
> non-compliant is not — the evidence is spread across every XML you've filed.
>
> This is a CLI that reads a folder of those XMLs and reports which SKUs need fixing,
> grouped by product rather than by occurrence. One broken SKU across 4,000 invoices
> is one row.
>
> No network calls, no runtime dependencies beyond the stdlib. Invoice data is
> commercially sensitive, so uploading it anywhere was never an option.
>
> AGPL: [link]

---

## Regras que valem para todas

- **Uma por vez.** Se você conseguiria trocar o nome da empresa e a mensagem continuar
  funcionando, ela não está personalizada.
- **Não invente número.** Não existe cliente, download ou depoimento ainda. A primeira
  alegação falsa que um contador pegar derruba tudo — é um mercado pequeno e que conversa.
- **Não use urgência falsa.** O prazo é real e é forte o bastante. "Últimas vagas" numa
  ferramenta gratuita é insulto à inteligência de quem lê.
- **Respeite descadastro.** Pediu pra não receber mais, acabou, e anota isso.
- **Sem envio em massa.** Além de ser spam, e-mail em lote com o mesmo corpo tem entrega
  ruim e queima seu domínio pro resto do ano.
